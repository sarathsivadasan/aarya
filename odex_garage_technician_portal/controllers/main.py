# -*- coding: utf-8 -*-
import logging

from odoo import http, fields, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class TechnicianPortalController(http.Controller):

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _check_access(self):
        if not request.env.user.has_group(
                'odex_garage_technician_portal.group_garage_technician'):
            raise AccessError(_('You do not have access to the Technician Portal.'))

    def _is_admin(self):
        """Administrator = Garage Technician Supervisor or Odoo system
        administrator. Checked independently of the technician group, so
        an administrator who is not himself a technician still gets in."""
        return request.env['account.analytic.line']._is_technician_admin()

    def _check_admin(self):
        if not self._is_admin():
            raise AccessError(_('You do not have administrator access to the '
                                'Technician Portal.'))

    def _error(self, message, status='error'):
        return {'status': status, 'message': message}

    def _task(self, task_id):
        """Resolve the related task. Related data (complaints, photos,
        parts, QC) hangs off the task, but the portal always ARRIVES here
        from an account.analytic.line - see _line()."""
        task = request.env['project.task'].browse(int(task_id))
        if not task.exists():
            raise UserError(_('Job not found.'))
        return task

    def _line(self, line_id):
        """The portal's primary record: one technician work record."""
        line = request.env['account.analytic.line'].browse(int(line_id))
        if not line.exists():
            raise UserError(_('Work record not found.'))
        return line

    # ------------------------------------------------------------------
    # dashboard
    # ------------------------------------------------------------------
    @http.route('/technician_portal/dashboard_counters', type='json', auth='user')
    def dashboard_counters(self):
        self._check_access()
        return request.env['account.analytic.line'].get_technician_dashboard_counters()

    @http.route('/technician_portal/access_info', type='json', auth='user')
    def access_info(self):
        """What the current user may do. The client action uses this to
        decide whether to render the administrator menu entry."""
        return {
            'is_technician': request.env.user.has_group(
                'odex_garage_technician_portal.group_garage_technician'),
            'is_admin': self._is_admin(),
            'user_name': request.env.user.name,
        }

    # ------------------------------------------------------------------
    # WORK RECORD LIST + DETAIL
    # The portal's primary query: MY account.analytic.line rows
    # (employees_id = me). task_id then tells us whether each one is a
    # Job Card (is_jobcard) or a Vehicle Inspection (is_vc), and all
    # related data is fetched through it.
    # ------------------------------------------------------------------
    @http.route('/technician_portal/inspection_list', type='json', auth='user')
    def inspection_list(self, search='', task_type='is_vc', status=None):
        """task_type: 'is_vc' | 'is_jobcard' | None (both).
        status: optional technician_status filter (not_started/running/
        paused/completed) - applied in Python since it's a non-stored
        compute on the line."""
        self._check_access()
        AAL = request.env['account.analytic.line']
        domain = AAL._my_lines_domain(task_type)
        if search:
            domain += ['|', '|',
                       ('task_id.name', 'ilike', search),
                       ('task_id.number', 'ilike', search),
                       ('product_id.name', 'ilike', search)]
        lines = AAL.search(domain, order='id desc')
        if status:
            lines = lines.filtered(lambda l: l.technician_status == status)
        return [l.to_portal_list_item() for l in lines]

    @http.route('/technician_portal/inspection_detail', type='json', auth='user')
    def inspection_detail(self, line_id):
        self._check_access()
        return self._line(line_id).to_portal_detail()

    # ------------------------------------------------------------------
    # BAY - the portal is a UI LAYER ONLY here.
    # Assignment goes through a normal ORM write on project.task.bay_id,
    # so the existing create()/write() occupancy validation and
    # job.card.bay.log Bay In/Out tracking run exactly as they do from
    # the Job Card / Vehicle Inspection form. Release calls the existing
    # action_release_bay(). No logging, validation, or state handling is
    # reimplemented here.
    # ------------------------------------------------------------------
    @http.route('/technician_portal/bay/list', type='json', auth='user')
    def bay_list(self, task_id=None):
        self._check_access()
        if 'job.card.bay' not in request.env:
            return {'supported': False, 'bays': []}
        bays = request.env['job.card.bay'].search([])
        current_id = False
        if task_id:
            task = self._task(task_id)
            if 'bay_id' in task._fields and task.bay_id:
                current_id = task.bay_id.id
        result = []
        for bay in bays:
            occupied = bay.is_occupied if 'is_occupied' in bay._fields else False
            result.append({
                'id': bay.id,
                'name': bay.display_name,
                # surfaced only as a hint for the dropdown - the backend
                # remains the source of truth and will reject an occupied
                # bay on write with its own message
                'is_occupied': bool(occupied) and bay.id != current_id,
                'is_current': bay.id == current_id,
            })
        return {'supported': True, 'bays': result}

    @http.route('/technician_portal/bay/assign', type='json', auth='user')
    def bay_assign(self, task_id, bay_id):
        self._check_access()
        task = self._task(task_id)
        if 'bay_id' not in task._fields:
            return self._error(_('Bay management is not available on this system.'))
        try:
            # plain ORM write - triggers the existing occupancy check and
            # Bay In/Out logging in project.task.write()
            task.write({'bay_id': int(bay_id)})
            return {'status': 'ok', 'bay_name': task.bay_id.display_name}
        except (UserError, ValidationError) as e:
            # backend validation is the source of truth - surface its
            # message verbatim (e.g. "This bay is not free.")
            return self._error(str(e))

    @http.route('/technician_portal/bay/release', type='json', auth='user')
    def bay_release(self, task_id):
        self._check_access()
        task = self._task(task_id)
        if not hasattr(task, 'action_release_bay'):
            return self._error(_('Bay release is not available on this system.'))
        try:
            task.action_release_bay()
            return {'status': 'ok'}
        except (UserError, ValidationError) as e:
            return self._error(str(e))

    # ------------------------------------------------------------------
    # complaints - job.requested.service (requested_services_ids), the
    # SAME One2many already used on Vehicle Inspection / Job Card.
    #
    # Read-only in the portal by design: Service, Instruction and Assign
    # Hours are all set upstream (on the Job Card / Vehicle Inspection
    # form). Assign Hours + the assignee list are sourced from the linked
    # timesheet lines (job_card_daily_report_ids), matched by product_id -
    # that link is created by add_service_to_timesheet_ext() in
    # job_card_extension, which stamps product_id onto the analytic line.
    # ------------------------------------------------------------------
    @http.route('/technician_portal/complaints/list', type='json', auth='user')
    def complaints_list(self, task_id):
        self._check_access()
        task = self._task(task_id)
        lines = request.env['job.requested.service'].search([('task_id', '=', task.id)])
        timesheets = task.job_card_daily_report_ids

        result = []
        for l in lines:
            # timesheet lines raised for this specific service
            matched = timesheets.filtered(
                lambda t, p=l.product_id: p and t.product_id.id == p.id)
            assignees = [{
                'name': t.employees_id.display_name,
                'hours': round(t.total_hours, 2),
            } for t in matched if t.employees_id]
            # Assign Hours comes from the timesheet where a line exists,
            # otherwise falls back to what was planned on the service.
            assign_hours = sum(matched.mapped('assign_hours')) if matched else l.assign_hours
            result.append({
                'id': l.id,
                'product': l.product_id.display_name if l.product_id else '',
                'remark': l.remark or '',
                'assign_hours': assign_hours,
                'assignees': assignees,
            })
        return result

    # ------------------------------------------------------------------
    # TIMER - writes the account.analytic.line fields directly.
    # Every route takes line_id: the work record IS the unit of work.
    # ------------------------------------------------------------------
    @http.route('/technician_portal/timer/start', type='json', auth='user')
    def timer_start(self, line_id):
        self._check_access()
        try:
            self._line(line_id).action_technician_start()
            return {'status': 'ok'}
        except (UserError, ValidationError) as e:
            return self._error(str(e))

    @http.route('/technician_portal/timer/pause', type='json', auth='user')
    def timer_pause(self, line_id):
        self._check_access()
        try:
            self._line(line_id).action_technician_pause()
            return {'status': 'ok'}
        except (UserError, ValidationError) as e:
            return self._error(str(e))

    @http.route('/technician_portal/timer/resume', type='json', auth='user')
    def timer_resume(self, line_id):
        self._check_access()
        try:
            self._line(line_id).action_technician_resume()
            return {'status': 'ok'}
        except (UserError, ValidationError) as e:
            return self._error(str(e))

    @http.route('/technician_portal/timer/complete', type='json', auth='user')
    def timer_complete(self, line_id):
        self._check_access()
        try:
            self._line(line_id).action_technician_end()
            return {'status': 'ok'}
        except (UserError, ValidationError) as e:
            return self._error(str(e))

    @http.route('/technician_portal/timer/request_more_time', type='json', auth='user')
    def timer_request_more_time(self, line_id, extra_hours=0.5, reason=''):
        self._check_access()
        try:
            self._line(line_id).action_request_more_time(extra_hours, reason)
            return {'status': 'ok'}
        except (UserError, ValidationError) as e:
            return self._error(str(e))

    # ------------------------------------------------------------------
    # parts - TWO different real models depending on task type:
    #   - Vehicle Inspection (is_vc): vehicle.inspection.part
    #     (inspection_part_ids on project.task, vehicle_inspection_report
    #     module). Fields confirmed: part_no (related, readonly),
    #     product_id, quantity. No status/remarks/type field exists on
    #     this model in the version reviewed.
    #   - Job Card (is_jobcard): jobcard.part.requisition (parts_request
    #     module). state is draft/approve/reject; creating a line already
    #     puts it in 'draft' = awaiting approval, no separate submit step.
    #     Has a real 'cost_type' selection (spare_parts/material/
    #     consumables/paint_material/sublet) - NOT the "Original"/etc
    #     values seen in a screenshot, which don't match either model as
    #     reviewed; flagging that mismatch rather than guessing at it.
    # ------------------------------------------------------------------
    @http.route('/technician_portal/parts/list', type='json', auth='user')
    def parts_list(self, task_id):
        """Part lines for this job.

        The `part` column carries the Char field you added to
        vehicle.inspection.part. Where a line has no value of its own but
        the linked Job Card / Vehicle Inspection does, that value is shown
        instead (part_source says where it came from) - so existing part
        data is visible from either side without being copied twice.
        """
        self._check_access()
        task = self._task(task_id)
        if task.is_vc or task.is_jobcard:
            lines = request.env['vehicle.inspection.part'].search(
                [('inspection_id', '=', task.id)])
            rows = [l.to_portal_dict() for l in lines]
            rows += self._related_part_rows(task, lines)
            return rows
        lines = request.env['jobcard.part.requisition'].search([('job_id', '=', task.id)])
        return [{
            'id': l.id, 'model': 'jobcard.part.requisition',
            'part_no': l.name,
            'part': l.part or '',
            'part_source': 'own',
            'part_editable': True,
            'product': l.product_id.display_name,
            'qty': l.qty, 'qty_available': l.qty_available,
            'state': l.state, 'remarks': l.remarks or '',
            'cost_type': dict(l._fields['cost_type'].selection or {}).get(l.cost_type, ''),
        } for l in lines]

    def _related_part_rows(self, task, own_lines):
        """Read-only rows for part data that exists on the linked Job Card
        / Vehicle Inspection but has no counterpart line on this task.

        These are shown so the technician sees everything that is already
        recorded for the vehicle, and are flagged is_related=True so the
        UI renders them without an edit box - editing them here would
        create a duplicate, which the brief explicitly forbids.
        """
        others = task._linked_part_tasks()
        if not others:
            return []
        related = request.env['vehicle.inspection.part'].sudo().search(
            [('inspection_id', 'in', others.ids)])
        own_products = own_lines.mapped('product_id').ids
        rows = []
        for line in related:
            if line.product_id and line.product_id.id in own_products:
                continue  # already represented by one of our own rows
            data = line.to_portal_dict()
            other_task = line.inspection_id
            data.update({
                'is_related': True,
                'part_editable': False,
                'origin': _('Job Card') if other_task.is_jobcard else _('Vehicle Inspection'),
                'origin_ref': (other_task.number if other_task.is_jobcard and other_task.number
                               else other_task.name) or '',
            })
            rows.append(data)
        return rows

    @http.route('/technician_portal/parts/update_line', type='json', auth='user')
    def parts_update_line(self, line_id, model='vehicle.inspection.part',
                          part=None, qty=None, remarks=None):
        """Save the technician's edits from the Parts tab.

        Writing `part` on a vehicle.inspection.part line propagates the
        value to the matching line on the linked Job Card / Vehicle
        Inspection (see models/vehicle_inspection_part.py). The
        propagation UPDATES the existing counterpart line; it never
        creates one, so nothing is duplicated.
        """
        self._check_access()
        if model not in ('vehicle.inspection.part', 'jobcard.part.requisition'):
            return self._error(_('Unknown part line type.'))
        line = request.env[model].browse(int(line_id))
        if not line.exists():
            return self._error(_('Part line not found.'))
        vals = {}
        if part is not None and 'part' in line._fields:
            vals['part'] = part
        if qty is not None:
            qty_field = 'quantity' if model == 'vehicle.inspection.part' else 'qty'
            try:
                vals[qty_field] = float(qty)
            except (TypeError, ValueError):
                return self._error(_('Quantity must be a number.'))
        if remarks is not None and 'remarks' in line._fields:
            vals['remarks'] = remarks
        if not vals:
            return {'status': 'ok', 'changed': False}
        try:
            line.write(vals)
        except (UserError, ValidationError, AccessError) as e:
            return self._error(str(e))
        if 'part' in vals:
            if model == 'vehicle.inspection.part':
                line._log_part_change(vals['part'])
            else:
                self._log_requisition_part(line, vals['part'])
        return {'status': 'ok', 'changed': True}

    def _log_requisition_part(self, line, value):
        if line.job_id:
            line.job_id.sudo()._add_log(
                'Parts Updated',
                _('Part information for %(product)s set to "%(value)s".') % {
                    'product': line.product_id.display_name or line.name or '',
                    'value': value or '-'})

    @http.route('/technician_portal/parts/products', type='json', auth='user')
    def parts_products(self, search=''):
        self._check_access()
        domain = [('name', 'ilike', search)] if search else []
        products = request.env['product.product'].search(domain, limit=30)
        return [{'id': p.id, 'name': p.display_name, 'qty_available': p.qty_available,
                 'uom_id': p.uom_id.id} for p in products]

    @http.route('/technician_portal/parts/add_line', type='json', auth='user')
    def parts_add_line(self, task_id, product_id, qty=1.0, remarks='', part=''):
        self._check_access()
        task = self._task(task_id)
        if task.is_fully_completed():
            return self._error(_('This job is already completed - parts can no longer be requested against it.'))
        product = request.env['product.product'].browse(int(product_id))
        if task.is_vc or task.is_jobcard:
            vals = {
                'inspection_id': task.id, 'product_id': product.id, 'quantity': qty,
            }
            Part = request.env['vehicle.inspection.part']
            if part and 'part' in Part._fields:
                vals['part'] = part
            line = Part.create(vals)
        else:
            vals = {
                'job_id': task.id, 'product_id': product.id,
                'description': product.display_name, 'qty': qty,
                'uom_id': product.uom_id.id, 'remarks': remarks,
                'register_no': task.vehicle_id.name if task.vehicle_id else '',
                'cc_vehicle_model': task.model_id.id if task.model_id else False,
            }
            Requisition = request.env['jobcard.part.requisition']
            if part and 'part' in Requisition._fields:
                vals['part'] = part
            line = Requisition.create(vals)
        try:
            qty_val = float(qty or 0.0)
        except (ValueError, TypeError):
            qty_val = 0.0
        task._add_log(
                 _("Parts Requested"),
                 _("Requested %s x %.2f.", product.display_name, qty_val),)
        task.move_to_waiting_for_parts()
        return {'status': 'ok', 'id': line.id}

    @http.route('/technician_portal/parts/delete_line', type='json', auth='user')
    def parts_delete_line(self, line_id, model='jobcard.part.requisition'):
        self._check_access()
        if model == 'vehicle.inspection.part':
            request.env['vehicle.inspection.part'].browse(int(line_id)).unlink()
            return {'status': 'ok'}
        line = request.env['jobcard.part.requisition'].browse(int(line_id))
        if line.state not in ('draft', 'reject'):
            return self._error(_('Only draft or rejected lines can be removed.'))
        line.unlink()
        return {'status': 'ok'}

    # ------------------------------------------------------------------
    # QC - real field is check_mark (Boolean), not a Pass/Fail selection.
    # ------------------------------------------------------------------
    @http.route('/technician_portal/qc/list', type='json', auth='user')
    def qc_list(self, task_id):
        self._check_access()
        lines = request.env['quality.checklist'].search([
            ('job_card_id', '=', int(task_id)), ('display_type', '=', False),
        ])
        return [{
            'id': l.id,
            'checklist': l.checklist_name_id.display_name if l.checklist_name_id else l.name,
            'check_mark': l.check_mark,
            'description': l.description or '',
            'has_image': bool(l.image),
        } for l in lines]

    @http.route('/technician_portal/qc/update', type='json', auth='user')
    def qc_update(self, line_id, check_mark=None, description=None, image=None):
        self._check_access()
        line = request.env['quality.checklist'].browse(int(line_id))
        vals = {}
        if check_mark is not None:
            vals['check_mark'] = check_mark
        if description is not None:
            vals['description'] = description
        if image:
            vals['image'] = image.split(',', 1)[1] if ',' in image else image
        line.write(vals)
        return {'status': 'ok', 'qc_passed': line.job_card_id.qc_passed}

    # ------------------------------------------------------------------
    # photos - reads/writes the real image1..image12 fields directly on
    # project.task (garage_management_odoo). No separate photo model or
    # storage: this IS the same record shown on Vehicle Inspection / Job
    # Card, so a technician's upload/edit here is immediately visible
    # there and vice versa.
    # ------------------------------------------------------------------
    @http.route('/technician_portal/photo/list', type='json', auth='user')
    def photo_list(self, task_id):
        self._check_access()
        task = self._task(task_id)
        slots = task.get_photo_slots()
        for slot in slots:
            slot['url'] = ('/web/image/project.task/%s/image%d' % (task.id, slot['slot'])
                            if slot['has_image'] else False)
        return slots

    @http.route('/technician_portal/photo/upload', type='json', auth='user')
    def photo_upload(self, task_id, slot, image, desc=None):
        self._check_access()
        task = self._task(task_id)
        if ',' in image:
            image = image.split(',', 1)[1]
        task.set_photo_slot(int(slot), image=image, desc=desc)
        return {'status': 'ok'}

    @http.route('/technician_portal/photo/update_desc', type='json', auth='user')
    def photo_update_desc(self, task_id, slot, desc):
        self._check_access()
        self._task(task_id).set_photo_slot(int(slot), desc=desc)
        return {'status': 'ok'}

    @http.route('/technician_portal/photo/delete', type='json', auth='user')
    def photo_delete(self, task_id, slot):
        self._check_access()
        self._task(task_id).clear_photo_slot(int(slot))
        return {'status': 'ok'}

    # ------------------------------------------------------------------
    # parts photos - a genuinely new feature (neither vehicle.inspection.
    # part nor jobcard.part.requisition has a photo field), so this is a
    # small dedicated model rather than a reuse of existing data.
    # ------------------------------------------------------------------
    @http.route('/technician_portal/parts_photo/list', type='json', auth='user')
    def parts_photo_list(self, task_id):
        self._check_access()
        photos = request.env['technician.part.photo'].search([('task_id', '=', int(task_id))])
        return [{
            'id': p.id, 'part_reference': p.part_reference or '',
            'description': p.description or '',
            'url': '/web/image/technician.part.photo/%s/image' % p.id,
        } for p in photos]

    @http.route('/technician_portal/parts_photo/upload', type='json', auth='user')
    def parts_photo_upload(self, task_id, image, part_reference='', description=''):
        self._check_access()
        task = self._task(task_id)
        if ',' in image:
            image = image.split(',', 1)[1]
        photo = request.env['technician.part.photo'].create({
            'task_id': task.id, 'image': image,
            'part_reference': part_reference, 'description': description,
        })
        return {'status': 'ok', 'id': photo.id}

    @http.route('/technician_portal/parts_photo/delete', type='json', auth='user')
    def parts_photo_delete(self, photo_id):
        self._check_access()
        request.env['technician.part.photo'].browse(int(photo_id)).unlink()
        return {'status': 'ok'}

    # ------------------------------------------------------------------
    # logs / notes
    # ------------------------------------------------------------------
    @http.route('/technician_portal/log/list', type='json', auth='user')
    def log_list(self, task_id):
        self._check_access()
        logs = request.env['technician.log'].search(
            [('task_id', '=', int(task_id))], order='log_date desc, id desc')
        return [l.to_portal_dict() for l in logs]

    @http.route('/technician_portal/note/list', type='json', auth='user')
    def note_list(self, task_id):
        self._check_access()
        notes = request.env['technician.note'].search(
            [('task_id', '=', int(task_id))], order='note_date desc')
        return [{'id': n.id, 'date': n.note_date and n.note_date.isoformat(),
                 'user': n.user_id.display_name, 'content': n.content} for n in notes]

    @http.route('/technician_portal/note/add', type='json', auth='user')
    def note_add(self, task_id, content):
        self._check_access()
        note = request.env['technician.note'].create({
            'task_id': self._task(task_id).id, 'content': content,
        })
        return {'status': 'ok', 'id': note.id}

    # ------------------------------------------------------------------
    # performance - aggregated directly from account.analytic.line
    # (job_card_daily_report_ids) for the current employee, across every
    # job card / inspection, not from per-task fields.
    # ------------------------------------------------------------------
    @http.route('/technician_portal/performance', type='json', auth='user')
    def performance(self):
        self._check_access()
        employee = request.env.user.employee_id
        if not employee:
            return {}

        from datetime import timedelta
        AAL = request.env['account.analytic.line']
        # compare against 'now' in the SAME convention the stored
        # datetimes use - see the note in models/account_analytic_line.py
        now = AAL._source_now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)

        base_domain = [('employees_id', '=', employee.id), ('is_end_time', '=', True)]

        completed_today = AAL.search_count(base_domain + [('end_datetime', '>=', today_start)])
        completed_week = AAL.search_count(base_domain + [('end_datetime', '>=', week_start)])
        month_lines = AAL.search(base_domain + [('end_datetime', '>=', month_start)])
        completed_month = len(month_lines)

        avg_time = (sum(month_lines.mapped('total_hours')) / len(month_lines)) if month_lines else 0.0
        assign_hours_sum = sum(month_lines.mapped('assign_hours'))
        actual_hours_sum = sum(month_lines.mapped('total_hours'))
        efficiency = round(min(assign_hours_sum / actual_hours_sum, 1.0) * 100, 1) if actual_hours_sum else 0.0

        # everything below starts from MY analytic lines, not from tasks
        my_lines = AAL.search(AAL._my_lines_domain())
        pending = len(my_lines.filtered(lambda l: l.technician_status == 'not_started'))
        paused = len(my_lines.filtered(lambda l: l.technician_status == 'paused'))

        today = now.date()
        threshold_hours = request.env.company.technician_late_job_threshold or 0.0
        threshold_days = threshold_hours / 24.0
        late_jobs = len(my_lines.filtered(
            lambda l: l.task_id.promise_date
            and l.task_id.promise_date + timedelta(days=threshold_days) < today
            and l.technician_status != 'completed'))

        chart = []
        for i in range(6, -1, -1):
            day_start = today_start - timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            day_lines = AAL.search(base_domain + [
                ('end_datetime', '>=', day_start), ('end_datetime', '<', day_end)])
            chart.append({'date': day_start.strftime('%a'),
                           'hours': round(sum(day_lines.mapped('total_hours')), 2),
                           'jobs': len(day_lines)})

        return {
            'completed_today': completed_today,
            'completed_week': completed_week,
            'completed_month': completed_month,
            'average_time': round(avg_time, 2),
            'efficiency': efficiency,
            'pending': pending,
            'paused': paused,
            'late_jobs': late_jobs,
            'chart': chart,
        }

    @http.route('/technician_portal/profile', type='json', auth='user')
    def profile(self):
        self._check_access()
        employee = request.env.user.employee_id
        if not employee:
            return {}
        return {
            'name': employee.name,
            'department': employee.department_id.display_name if employee.department_id else '',
            'designation': employee.job_id.display_name if employee.job_id else '',
            'workshop_position': dict(employee._fields['workshop_position_type'].selection or {}).get(
                employee.workshop_position_type, '') if 'workshop_position_type' in employee._fields else '',
            'email': employee.work_email or employee.user_id.email or '',
            'phone': employee.mobile_phone or employee.work_phone or '',
            'skills': employee.technician_skills or '',
            'experience_years': employee.technician_experience_years,
            'image_url': '/web/image/hr.employee/%s/image_1920' % employee.id,
        }

    # ==================================================================
    # ADMINISTRATOR - ALL ASSIGNED JOBS (requirement 3)
    # ==================================================================
    # The query starts from account.analytic.line, which is where a
    # technician assignment actually lives, so a job shows up here
    # whether it originated as a Job Card or as a Vehicle Inspection -
    # no second code path, no union of two lists.
    #
    # Pause / Resume / Stop call the SAME _do_*() internals the
    # technician's own buttons call (see models/account_analytic_line.py),
    # so the status and the time tracking move identically. The only
    # differences are the permission check and the log entry, which is
    # flagged is_admin_action and names both the technician and the
    # administrator who acted.
    # ------------------------------------------------------------------
    @http.route('/technician_portal/admin/counters', type='json', auth='user')
    def admin_counters(self):
        self._check_admin()
        return request.env['account.analytic.line'].sudo().get_admin_dashboard_counters()

    @http.route('/technician_portal/admin/technicians', type='json', auth='user')
    def admin_technicians(self):
        """Technicians who actually have work assigned - used to populate
        the filter dropdown."""
        self._check_admin()
        AAL = request.env['account.analytic.line'].sudo()
        lines = AAL.search(AAL._all_lines_domain())
        employees = lines.mapped('employees_id')
        return [{'id': e.id, 'name': e.display_name}
                for e in employees.sorted(lambda e: e.display_name or '')]

    @http.route('/technician_portal/admin/jobs', type='json', auth='user')
    def admin_jobs(self, search='', task_type=None, status=None, technician_id=None):
        """Every assigned job in the workshop.

        task_type: 'is_vc' | 'is_jobcard' | None (both)
        status:    not_started | running | paused | completed | None
        technician_id: restrict to one technician
        """
        self._check_admin()
        AAL = request.env['account.analytic.line'].sudo()
        domain = AAL._all_lines_domain(task_type)
        if technician_id:
            domain.append(('employees_id', '=', int(technician_id)))
        if search:
            domain += ['|', '|', '|',
                       ('task_id.name', 'ilike', search),
                       ('task_id.number', 'ilike', search),
                       ('product_id.name', 'ilike', search),
                       ('employees_id.name', 'ilike', search)]
        lines = AAL.search(domain, order='id desc')
        if status:
            lines = lines.filtered(lambda l: l.technician_status == status)
        return [l.to_admin_list_item() for l in lines]

    def _admin_timer(self, line_id, method):
        self._check_admin()
        line = request.env['account.analytic.line'].sudo().browse(int(line_id))
        if not line.exists():
            return self._error(_('Work record not found.'))
        try:
            getattr(line, method)()
        except (UserError, ValidationError, AccessError) as e:
            return self._error(str(e))
        return {'status': 'ok', 'job': line.to_admin_list_item()}

    @http.route('/technician_portal/admin/timer/start', type='json', auth='user')
    def admin_timer_start(self, line_id):
        return self._admin_timer(line_id, 'action_admin_start')

    @http.route('/technician_portal/admin/timer/pause', type='json', auth='user')
    def admin_timer_pause(self, line_id):
        return self._admin_timer(line_id, 'action_admin_pause')

    @http.route('/technician_portal/admin/timer/resume', type='json', auth='user')
    def admin_timer_resume(self, line_id):
        return self._admin_timer(line_id, 'action_admin_resume')

    @http.route('/technician_portal/admin/timer/stop', type='json', auth='user')
    def admin_timer_stop(self, line_id):
        return self._admin_timer(line_id, 'action_admin_end')

    @http.route('/technician_portal/admin/logs', type='json', auth='user')
    def admin_logs(self, line_id=None, task_id=None, technician_id=None, limit=100):
        """Activity log. Every Start / Pause / Resume / Stop is in here,
        with the job reference, the technician, the action, the timestamp
        and the user who performed it."""
        self._check_admin()
        domain = []
        if line_id:
            domain.append(('analytic_line_id', '=', int(line_id)))
        if task_id:
            domain.append(('task_id', '=', int(task_id)))
        if technician_id:
            domain.append(('technician_id', '=', int(technician_id)))
        logs = request.env['technician.log'].sudo().search(
            domain, order='log_date desc, id desc', limit=int(limit))
        return [l.to_portal_dict() for l in logs]

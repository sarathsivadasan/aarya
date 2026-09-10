/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

const MONTHS = ["January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"];

publicWidget.registry.OdexBookingWizard = publicWidget.Widget.extend({
    selector: "#owb_wizard",
    events: {
        "click #owb_next_btn": "_onNext",
        "click #owb_back_btn": "_onBack",
        "click #owb_cal_prev": "_onPrevMonth",
        "click #owb_cal_next": "_onNextMonth",
        "change #owb_branch": "_onCompanyChange",
        "click .owb-cal-day.owb-selectable": "_onDayClick",
        "click .owb-slot.owb-slot-bookable": "_onSlotClick",
        "blur #owb_mobile": "_onCustomerLookup",
        "blur #owb_phone": "_onCustomerLookup",
        "blur #owb_email": "_onCustomerLookup",
        "change #owb_make": "_onMakeChange",
        "click .owb-vehicle-card": "_onVehicleCardClick",
        "click #owb_add_new_vehicle": "_onAddNewVehicle",
        "input #owb_note": "_onCounters",
        "input #owb_name, #owb_mobile, #owb_plate, #owb_model": "_refreshNext",
        "change #owb_service, #owb_model": "_refreshNext",
        "input #owb_complaint": "_refreshComplaint",
        "change #owb_terms": "_onTermsChange",
        "click #owb_confirm_btn": "_onSubmit",
    },

    start() {
        const today = new Date();
        this.state = {
            step: 1,
            year: today.getFullYear(),
            month: today.getMonth(),
            days: {},
            reasons: {},
            date: null,
            slotId: null,
            slotDate: null,
            slotHour: null,
            slotLabel: "",
            existingVehicleId: null,
            existingName: null,
        };
        this._preselectOwnVehicle();
        this._renderCalendar();
        this._loadMonth();
        return this._super(...arguments);
    },

    // ------------------------------------------------------------------
    // Step navigation
    // ------------------------------------------------------------------
    _showStep(step) {
        this.state.step = step;
        this.el.querySelectorAll(".owb-pane").forEach((pane) => {
            pane.classList.toggle("d-none", parseInt(pane.dataset.pane) !== step);
        });
        document.querySelectorAll(".owb-step").forEach((el) => {
            const n = parseInt(el.dataset.step);
            el.classList.toggle("owb-step-active", n === step);
            el.classList.toggle("owb-step-done", n < step);
        });
        this.el.querySelector("#owb_back_btn").classList.toggle("d-none", step === 1);
        this.el.querySelector("#owb_next_btn").classList.toggle("d-none", step === 5);
        this.el.querySelector("#owb_step_error").textContent = "";
        this._refreshNext();
        window.scrollTo({ top: 0, behavior: "smooth" });
    },

    _stepValid() {
        const s = this.state;
        const val = (id) => (this.el.querySelector(id)?.value || "").trim();
        switch (s.step) {
            case 1: return !!s.date;
            case 2: return !!s.slotId;
            case 3: {
                if (!val("#owb_name") || !val("#owb_mobile")) return false;
                if (s.existingVehicleId) return true;
                return !!val("#owb_plate") && !!val("#owb_model");
            }
            case 4: return !!val("#owb_service") && !!val("#owb_complaint");
            default: return true;
        }
    },

    _refreshNext() {
        const btn = this.el.querySelector("#owb_next_btn");
        if (btn) btn.disabled = !this._stepValid();
    },

    _onNext() {
        if (!this._stepValid()) return;
        if (this.state.step === 4) this._renderSummary();
        this._showStep(this.state.step + 1);
    },

    _onBack() {
        if (this.state.step > 1) this._showStep(this.state.step - 1);
    },

    // ------------------------------------------------------------------
    // Step 1: calendar
    // ------------------------------------------------------------------
    _companyId() {
        const value = parseInt(this.el.querySelector("#owb_branch")?.value);
        return Number.isInteger(value) ? value : null;
    },

    async _loadMonth() {
        const companyId = this._companyId();
        if (!companyId) {
            this.state.days = {};
            this._renderCalendar();
            this._showNoCompany();
            return;
        }
        const { year, month } = this.state;
        try {
            const result = await rpc("/booking/api/month", {
                company_id: companyId,
                year: year, month: month + 1,
            });
            this.state.days = result.days || {};
            this.state.reasons = result.reasons || {};
            this._setNotice(this._monthNotice(result));
        } catch (error) {
            // A failed request must never masquerade as "everything closed".
            this.state.days = {};
            this.state.reasons = {};
            this._setNotice((error && error.data && error.data.message) ||
                "Could not load availability. Please try again.");
        }
        this._renderCalendar();
    },

    _setNotice(message) {
        const box = this.el.querySelector("#owb_step_error");
        if (box) {
            box.textContent = message || "";
        }
    },

    // Explain an empty month instead of showing a silently grey calendar.
    _monthNotice(result) {
        if (result.error === "no_company") {
            return "No workshop is available for online booking yet.";
        }
        const days = result.days || {};
        const open = Object.values(days).filter(
            (state) => state === "available" || state === "limited");
        if (open.length) {
            return "";
        }
        const summary = result.summary || {};
        if (summary.no_slots) {
            return "No time slots have been published for this month. " +
                "Try the next month, or contact us to book by phone.";
        }
        if (summary.beyond_horizon) {
            return "This month is beyond the booking window. " +
                "Please choose an earlier date.";
        }
        if (summary.notice_window) {
            return "The remaining slots are inside the minimum notice " +
                "period. Please choose a later date.";
        }
        if (summary.capacity) {
            return "Every slot this month is fully booked. " +
                "Please try another month.";
        }
        if (summary.holiday) {
            return "The workshop is closed for this whole month.";
        }
        return "No availability this month — please try another month.";
    },

    _showNoCompany() {
        const box = this.el.querySelector("#owb_no_branch");
        if (box) box.classList.remove("d-none");
    },

    _renderCalendar() {
        const { year, month, days } = this.state;
        this.el.querySelector("#owb_cal_title").textContent =
            `${MONTHS[month]} ${year}`;
        const grid = this.el.querySelector("#owb_cal_days");
        grid.innerHTML = "";
        const first = new Date(year, month, 1);
        const offset = (first.getDay() + 6) % 7; // Monday first
        const numDays = new Date(year, month + 1, 0).getDate();
        for (let i = 0; i < offset; i++) {
            grid.appendChild(document.createElement("div"));
        }
        for (let d = 1; d <= numDays; d++) {
            const iso = `${year}-${String(month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
            const status = days[iso] || "closed";
            const cell = document.createElement("div");
            cell.className = "owb-cal-day";
            cell.dataset.date = iso;
            const reason = (this.state.reasons || {})[iso];
            if (reason) {
                cell.title = {
                    no_slots: "No slots published for this day",
                    holiday: "Workshop closed",
                    blocked: "All slots blocked",
                    past: "Date has passed",
                    beyond_horizon: "Beyond the booking window",
                    notice_window: "Too close to the appointment time",
                    capacity: "Fully booked",
                }[reason] || reason;
            }
            cell.innerHTML = `<span>${d}</span><span class="owb-day-dot owb-day-${status}"></span>`;
            if (["available", "limited"].includes(status)) {
                cell.classList.add("owb-selectable");
            } else {
                cell.classList.add("owb-disabled");
            }
            if (this.state.date === iso) cell.classList.add("owb-day-selected");
            grid.appendChild(cell);
        }
    },

    _onPrevMonth() {
        if (--this.state.month < 0) { this.state.month = 11; this.state.year--; }
        this._loadMonth();
    },
    _onNextMonth() {
        if (++this.state.month > 11) { this.state.month = 0; this.state.year++; }
        this._loadMonth();
    },
    _onCompanyChange() {
        this.state.date = null;
        this.state.slotId = null;
        this._loadMonth();
        this._refreshNext();
    },

    _onDayClick(ev) {
        const cell = ev.currentTarget;
        this.state.date = cell.dataset.date;
        this.state.slotId = null;
        this.el.querySelectorAll(".owb-cal-day").forEach((c) =>
            c.classList.toggle("owb-day-selected", c === cell));
        this._refreshNext();
        this._loadSlots();
    },

    // ------------------------------------------------------------------
    // Step 2: slots
    // ------------------------------------------------------------------
    async _loadSlots() {
        const companyId = this._companyId();
        if (!companyId || !this.state.date) return;
        const loading = this.el.querySelector("#owb_slots_loading");
        loading.classList.remove("d-none");
        let result = { slots: [] };
        try {
            result = await rpc("/booking/api/slots", {
                company_id: companyId, date: this.state.date,
            });
        } catch {
            result = { slots: [] };
        }
        loading.classList.add("d-none");
        const d = new Date(this.state.date + "T00:00:00");
        this.el.querySelector("#owb_slot_subtitle").textContent =
            `Available slots for ${d.toLocaleDateString(undefined,
                { weekday: "short", day: "numeric", month: "long", year: "numeric" })}`;
        if (result.duration) {
            const mins = Math.round(result.duration * 60);
            this.el.querySelector("#owb_duration_strip").innerHTML =
                `<i class="fa fa-clock-o me-2"></i>Each slot duration is ${mins} minutes`;
        }
        const morning = this.el.querySelector("#owb_slots_morning");
        const afternoon = this.el.querySelector("#owb_slots_afternoon");
        morning.innerHTML = afternoon.innerHTML = "";
        let passed = 0;
        for (const slot of result.slots || []) {
            const el = document.createElement("div");
            const stateLabel = { available: "Available", limited: "Limited",
                full: "Fully Booked", blocked: "Blocked" }[slot.state] || "";
            // Tell the truth about WHY a slot cannot be taken: a time that has
            // already passed is not "Fully Booked".
            const tone = slot.bookable ? slot.state
                : (["passed", "too_soon", "beyond_horizon"].includes(slot.reason)
                    ? "past" : "full");
            el.className = `owb-slot owb-slot-${tone}`;
            if (slot.bookable) {
                el.classList.add("owb-slot-bookable");
            } else if (slot.reason === "passed" || slot.reason === "too_soon") {
                passed++;
            }
            el.dataset.date = slot.date;
            el.dataset.hourFrom = slot.hour_from;
            el.dataset.label = `${slot.label} - ${slot.label_to}`;
            el.innerHTML = `<div class="fw-semibold">${slot.label}</div>
                <div class="owb-slot-state">${
                    slot.bookable ? stateLabel : (slot.reason_label || "Unavailable")
                }</div>`;
            (slot.period === "morning" ? morning : afternoon).appendChild(el);
        }
        // A day that is mostly gone deserves a nudge rather than a wall of red.
        const note = this.el.querySelector("#owb_slot_note");
        if (note) {
            const total = (result.slots || []).length;
            note.textContent = passed && passed === total
                ? "All of today's times have passed — please choose another date."
                : (passed
                    ? `${passed} earlier time${passed > 1 ? "s have" : " has"} passed today.`
                    : "");
            note.classList.toggle("d-none", !passed);
        }
        if (!morning.children.length) morning.innerHTML =
            '<div class="text-muted small">No morning slots</div>';
        if (!afternoon.children.length) afternoon.innerHTML =
            '<div class="text-muted small">No afternoon slots</div>';
    },

    _onSlotClick(ev) {
        const el = ev.currentTarget;
        this.state.slotDate = el.dataset.date;
        this.state.slotHour = parseFloat(el.dataset.hourFrom);
        this.state.slotId = true;   // "a time is chosen"
        this.state.slotLabel = el.dataset.label;
        this.el.querySelectorAll(".owb-slot").forEach((s) =>
            s.classList.toggle("owb-slot-selected", s === el));
        this._refreshNext();
    },

    // ------------------------------------------------------------------
    // Step 3: customer lookup + vehicles
    // ------------------------------------------------------------------
    async _onCustomerLookup() {
        const mobile = this.el.querySelector("#owb_mobile").value.trim();
        const phone = this.el.querySelector("#owb_phone").value.trim();
        const email = this.el.querySelector("#owb_email").value.trim();
        if (!mobile && !phone && !email) return;
        const result = await rpc("/booking/api/customer_lookup",
            { mobile, phone, email });
        const banner = this.el.querySelector("#owb_existing_banner");
        const block = this.el.querySelector("#owb_existing_vehicles");
        if (!result.found) {
            banner.classList.add("d-none");
            block.classList.add("d-none");
            this.state.existingVehicleId = null;
            this._showNewVehicle(true);
            return;
        }
        this.state.existingName = result.name;
        banner.classList.remove("d-none");
        this.el.querySelector("#owb_existing_name").textContent = result.name;
        const nameInput = this.el.querySelector("#owb_name");
        if (!nameInput.value.trim()) nameInput.value = result.name;
        const cards = this.el.querySelector("#owb_vehicle_cards");
        cards.innerHTML = "";
        if (result.vehicles.length) {
            for (const v of result.vehicles) {
                const card = document.createElement("div");
                card.className = "owb-vehicle-card p-3";
                card.dataset.vehicleId = v.id;
                card.dataset.vehicleName = v.name;
                card.innerHTML = `<div class="d-flex align-items-center gap-2">
                    <i class="fa fa-car text-primary"></i>
                    <div><div class="fw-semibold">${v.make} ${v.model} ${v.year || ""}</div>
                    <div class="small text-muted">${v.plate || "No plate"}</div></div>
                    <i class="fa fa-check-circle ms-auto owb-vehicle-check"></i></div>`;
                cards.appendChild(card);
            }
            block.classList.remove("d-none");
            this._showNewVehicle(false);
        } else {
            block.classList.add("d-none");
            this._showNewVehicle(true);
        }
        this._refreshNext();
    },

    // Signed-in customers: hide the new-vehicle form and pick their car.
    _preselectOwnVehicle() {
        const cards = this.el.querySelectorAll("#owb_own_wrap .owb-vehicle-card");
        if (!cards.length) {
            return;
        }
        this._showNewVehicle(false);
        if (cards.length === 1) {
            cards[0].click();
        }
    },

    _showNewVehicle(show) {
        this.el.querySelector("#owb_new_vehicle").classList.toggle("d-none", !show);
        if (show) this.state.existingVehicleId = null;
    },

    _onVehicleCardClick(ev) {
        const card = ev.currentTarget;
        this.state.existingVehicleId = parseInt(card.dataset.vehicleId);
        this.state.existingVehicleName = card.dataset.vehicleName;
        this.el.querySelectorAll(".owb-vehicle-card").forEach((c) =>
            c.classList.toggle("owb-vehicle-selected", c === card));
        this._showNewVehicle(false);
        this._refreshNext();
    },

    _onAddNewVehicle() {
        this.el.querySelectorAll(".owb-vehicle-card").forEach((c) =>
            c.classList.remove("owb-vehicle-selected"));
        this.state.existingVehicleId = null;
        this._showNewVehicle(true);
        this._refreshNext();
    },

    async _onMakeChange() {
        const brandId = this.el.querySelector("#owb_make").value;
        const modelSelect = this.el.querySelector("#owb_model");
        this._refreshNext();
        modelSelect.innerHTML = '<option value="">Select Model</option>';
        modelSelect.disabled = !brandId;
        if (!brandId) return;
        const result = await rpc("/booking/api/models", { brand_id: brandId });
        for (const m of result.models || []) {
            const opt = document.createElement("option");
            opt.value = m.id;
            opt.textContent = m.name;
            modelSelect.appendChild(opt);
        }
    },

    // ------------------------------------------------------------------
    // Step 4/5
    // ------------------------------------------------------------------
    _onCounters() {
        const complaint = this.el.querySelector("#owb_complaint");
        const note = this.el.querySelector("#owb_note");
        this.el.querySelector("#owb_complaint_count").textContent = complaint.value.length;
        this.el.querySelector("#owb_note_count").textContent = note.value.length;
    },

    _refreshComplaint() {
        this._onCounters();
        this._refreshNext();
    },

    _renderSummary() {
        const val = (id) => (this.el.querySelector(id)?.value || "").trim();
        const text = (id) => {
            const el = this.el.querySelector(id);
            return el && el.selectedIndex >= 0
                ? el.options[el.selectedIndex].textContent : "";
        };
        const d = new Date(this.state.date + "T00:00:00");
        let vehicleLabel;
        if (this.state.existingVehicleId) {
            vehicleLabel = this.state.existingVehicleName;
        } else {
            vehicleLabel = `${text("#owb_make")} ${text("#owb_model")} (${val("#owb_plate")})`;
        }
        const rows = [
            ["fa-calendar", "Date", d.toLocaleDateString(undefined,
                { weekday: "long", day: "numeric", month: "long", year: "numeric" })],
            ["fa-clock-o", "Time", this.state.slotLabel],
            ["fa-map-marker", "Workshop", text("#owb_branch")],
            ["fa-user", "Customer Name", val("#owb_name")],
            ["fa-phone", "Mobile Number", "+971 " + val("#owb_mobile")],
            ["fa-envelope-o", "Email", val("#owb_email") || "-"],
            ["fa-car", "Vehicle", vehicleLabel],
            ["fa-wrench", "Service Type", text("#owb_service")],
            ["fa-comment-o", "Issue / Description", val("#owb_complaint")],
        ];
        this.el.querySelector("#owb_summary").innerHTML = rows.map(
            ([icon, label, value]) => `
            <div class="d-flex gap-3 py-2 border-bottom owb-summary-row">
                <i class="fa ${icon} text-primary mt-1"></i>
                <div><div class="small text-muted">${label}</div>
                <div class="fw-semibold">${this._escape(value)}</div></div>
            </div>`).join("");
    },

    _escape(s) {
        const div = document.createElement("div");
        div.textContent = s || "";
        return div.innerHTML;
    },

    _onTermsChange() {
        this.el.querySelector("#owb_confirm_btn").disabled =
            !this.el.querySelector("#owb_terms").checked;
    },

    async _onSubmit() {
        const btn = this.el.querySelector("#owb_confirm_btn");
        const errorBox = this.el.querySelector("#owb_submit_error");
        errorBox.classList.add("d-none");
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Confirming...';
        const val = (id) => (this.el.querySelector(id)?.value || "").trim();
        const payload = {
            company_id: this._companyId(),
            date: this.state.slotDate,
            hour_from: this.state.slotHour,
            service_type_id: val("#owb_service"),
            complaint: val("#owb_complaint"),
            note: val("#owb_note"),
            referral_source: val("#owb_referral"),
            pickup_location_id: val("#owb_pickup"),
            drop_location_id: val("#owb_drop"),
            customer: {
                name: val("#owb_name"),
                mobile: "+971" + val("#owb_mobile").replace(/\s/g, ""),
                phone: val("#owb_phone"),
                email: val("#owb_email"),
                country_id: val("#owb_country"),
            },
            vehicle: this.state.existingVehicleId
                ? { id: this.state.existingVehicleId }
                : {
                    model_id: val("#owb_model"),
                    plate: val("#owb_plate"),
                    code_id: val("#owb_plate_code"),
                    emirate_id: val("#owb_emirate"),
                    vin: val("#owb_vin"),
                    engine_number: val("#owb_engine"),
                    year: val("#owb_year"),
                    color: val("#owb_color"),
                    cylinders: val("#owb_cylinders"),
                    odometer: val("#owb_odometer"),
                },
        };
        try {
            const result = await rpc("/booking/api/submit", payload);
            if (result.success) {
                window.location.href = result.redirect;
                return;
            }
            errorBox.textContent = result.error || "Something went wrong. Please try again.";
            errorBox.classList.remove("d-none");
        } catch (error) {
            // Show what the server actually said when it says anything.
            const message = error?.data?.message || error?.message;
            errorBox.textContent = message ||
                "We could not reach the server. Please try again.";
            errorBox.classList.remove("d-none");
        }
        btn.disabled = false;
        btn.textContent = "Confirm Booking";
    },
});

export default publicWidget.registry.OdexBookingWizard;

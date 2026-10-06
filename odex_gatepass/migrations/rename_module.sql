-- ============================================================
-- One-time migration: rename module gate_pass -> odex_gatepass
-- Run ONCE on the production database while Odoo is STOPPED.
--   psql -d <dbname> -f rename_module.sql
-- ============================================================

BEGIN;

-- 1. The module record itself
UPDATE ir_module_module
   SET name = 'odex_gatepass'
 WHERE name = 'gate_pass';

-- 2. Every XML ID owned by the module (views, menus, groups, ACLs, sequence...)
UPDATE ir_model_data
   SET module = 'odex_gatepass'
 WHERE module = 'gate_pass';

-- 3. base's registration record for the module
UPDATE ir_model_data
   SET name = 'module_odex_gatepass'
 WHERE module = 'base'
   AND name = 'module_gate_pass';

-- 4. Any other installed module that declares a dependency on it
UPDATE ir_module_module_dependency
   SET name = 'odex_gatepass'
 WHERE name = 'gate_pass';

COMMIT;

-- Verify (should return 1 row, state 'installed'):
-- SELECT name, state FROM ir_module_module WHERE name = 'odex_gatepass';

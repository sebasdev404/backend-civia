ALTER TABLE citizens ADD COLUMN IF NOT EXISTS contact_origin VARCHAR(40);
ALTER TABLE citizens ADD COLUMN IF NOT EXISTS origin_observation TEXT;
-- Formatting only: audited existing numbers have valid Colombian national lengths.
-- Invalid legacy numbers or duplicate canonical numbers abort the entire migration.
UPDATE citizens SET phone = NULL WHERE phone IS NOT NULL AND btrim(phone) = '';
UPDATE citizens SET phone = '+57' || right(regexp_replace(phone, '[^0-9]', '', 'g'), 10)
WHERE phone IS NOT NULL AND regexp_replace(phone, '[^0-9]', '', 'g') ~ '^(57)?(3[0-9]{9}|60[1245678][0-9]{7})$';
ALTER TABLE citizens ADD CONSTRAINT ck_citizens_colombian_phone
CHECK (phone IS NULL OR phone ~ '^\+57(3[0-9]{9}|60[1245678][0-9]{7})$');
DROP INDEX IF EXISTS ix_citizens_phone;
CREATE UNIQUE INDEX ix_citizens_phone ON citizens(phone);

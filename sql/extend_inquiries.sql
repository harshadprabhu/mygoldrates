-- Extend inquiries table with enrichment fields captured at sign-in/sign-up.
-- Run once in Supabase SQL Editor.

ALTER TABLE inquiries
  ADD COLUMN IF NOT EXISTS google_id       text,
  ADD COLUMN IF NOT EXISTS google_picture  text,
  ADD COLUMN IF NOT EXISTS google_locale   text,
  ADD COLUMN IF NOT EXISTS age             smallint,
  ADD COLUMN IF NOT EXISTS gender          text,
  ADD COLUMN IF NOT EXISTS signup_source   text;   -- 'google' | 'form' | 'gate_google' | 'gate_form'

-- Update upsert_subscriber RPC to accept new fields.
-- Drop and recreate so the signature matches.
DROP FUNCTION IF EXISTS upsert_subscriber(jsonb);

CREATE OR REPLACE FUNCTION upsert_subscriber(payload jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  tok  uuid;
  rec  inquiries%ROWTYPE;
BEGIN
  SELECT * INTO rec FROM inquiries
  WHERE lower(email) = lower(payload->>'email') LIMIT 1;

  IF rec.id IS NULL THEN
    tok := gen_random_uuid();
    INSERT INTO inquiries (
      name, email, phone, country, state, city, zip, area,
      offers_optin, unsub_token, signup_method,
      google_id, google_picture, google_locale,
      age, gender, signup_source
    ) VALUES (
      payload->>'name', lower(payload->>'email'), payload->>'phone',
      COALESCE(payload->>'country','India'),
      payload->>'state', payload->>'city', payload->>'zip', payload->>'area',
      COALESCE((payload->>'offers_optin')::boolean, true),
      tok, payload->>'signup_method',
      payload->>'google_id', payload->>'google_picture', payload->>'google_locale',
      (payload->>'age')::smallint, payload->>'gender',
      payload->>'signup_source'
    )
    RETURNING * INTO rec;
  ELSE
    -- Merge: update non-null incoming fields only, never overwrite with null.
    UPDATE inquiries SET
      name           = COALESCE(payload->>'name', name),
      phone          = COALESCE(payload->>'phone', phone),
      state          = COALESCE(payload->>'state', state),
      city           = COALESCE(payload->>'city', city),
      zip            = COALESCE(payload->>'zip', zip),
      area           = COALESCE(payload->>'area', area),
      google_id      = COALESCE(payload->>'google_id', google_id),
      google_picture = COALESCE(payload->>'google_picture', google_picture),
      google_locale  = COALESCE(payload->>'google_locale', google_locale),
      age            = COALESCE((payload->>'age')::smallint, age),
      gender         = COALESCE(payload->>'gender', gender),
      signup_source  = COALESCE(payload->>'signup_source', signup_source),
      signup_method  = COALESCE(payload->>'signup_method', signup_method)
    WHERE id = rec.id
    RETURNING * INTO rec;
  END IF;

  RETURN jsonb_build_object('unsub_token', rec.unsub_token, 'id', rec.id);
END;
$$;

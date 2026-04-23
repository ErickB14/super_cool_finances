-- ============================================================
--  DATABASE SETUP SCRIPT
--  PostgreSQL
-- ============================================================

-- Extension required for UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ------------------------------------------------------------
--  TABLE: users
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL      PRIMARY KEY,
    username      VARCHAR     NOT NULL UNIQUE,
    password_hash VARCHAR     NOT NULL,
    role          VARCHAR     NOT NULL DEFAULT 'customer',
    created_at    TIMESTAMP   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_users_id       ON users (id);
CREATE INDEX IF NOT EXISTS ix_users_username ON users (username);

-- ------------------------------------------------------------
--  TABLE: accounts
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS accounts (
    id         SERIAL          PRIMARY KEY,
    user_id    INTEGER         NOT NULL REFERENCES users (id),
    uuid       UUID            NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    owner      VARCHAR         NOT NULL,
    balance    NUMERIC(12, 2)  NOT NULL DEFAULT 0,
    created_at TIMESTAMP       NOT NULL DEFAULT now(),
    CONSTRAINT ck_accounts_balance_non_negative CHECK (balance >= 0)
);

CREATE INDEX IF NOT EXISTS ix_accounts_id   ON accounts (id);
CREATE INDEX IF NOT EXISTS ix_accounts_user_id ON accounts (user_id);
CREATE INDEX IF NOT EXISTS ix_accounts_uuid ON accounts (uuid);

-- ------------------------------------------------------------
--  TABLE: balance_hst
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS balance_hst (
    id              SERIAL          PRIMARY KEY,
    account_uuid    UUID            NOT NULL REFERENCES accounts (uuid),
    ttk_tracking_id VARCHAR         DEFAULT gen_random_uuid()::TEXT,
    disposable      NUMERIC(12, 2)  NOT NULL,
    type_tx         VARCHAR         NOT NULL,
    amount_tx       NUMERIC(12, 2)  NOT NULL,
    cdate           TIMESTAMP       NOT NULL DEFAULT now(),
    status_tx       VARCHAR         NOT NULL,
    description     VARCHAR,
    CONSTRAINT ck_balance_hst_disposable_non_negative CHECK (disposable >= 0),
    CONSTRAINT ck_balance_hst_amount_tx_positive CHECK (amount_tx > 0)
);

CREATE INDEX IF NOT EXISTS ix_balance_hst_id           ON balance_hst (id);
CREATE INDEX IF NOT EXISTS ix_balance_hst_account_uuid ON balance_hst (account_uuid);
CREATE INDEX IF NOT EXISTS ix_balance_hst_ttk_tracking_id ON balance_hst (ttk_tracking_id);

-- ------------------------------------------------------------
--  TABLE: refresh_tokens
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id         SERIAL       PRIMARY KEY,
    user_id    INTEGER      NOT NULL REFERENCES users (id),
    token      VARCHAR      NOT NULL UNIQUE,
    expires_at TIMESTAMP    NOT NULL,
    revoked    BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP    NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_refresh_tokens_id      ON refresh_tokens (id);
CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON refresh_tokens (user_id);

-- ------------------------------------------------------------
--  SEED: default users + test account with balance 100
-- ------------------------------------------------------------
DO $$
DECLARE
    v_user_id INTEGER;
BEGIN
    INSERT INTO users (username, password_hash, role)
    VALUES
        ('admin', crypt('admin123', gen_salt('bf')), 'admin'),
        ('alice', crypt('alice123', gen_salt('bf')), 'customer'),
        ('bob', crypt('bob123', gen_salt('bf')), 'customer')
    ON CONFLICT (username) DO NOTHING;

    SELECT id INTO v_user_id FROM users WHERE username = 'alice';

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Could not resolve seed user alice';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM accounts
        WHERE user_id = v_user_id
          AND owner = 'Test Account'
    ) THEN
        INSERT INTO accounts (user_id, uuid, owner, balance)
        VALUES (v_user_id, gen_random_uuid(), 'Test Account', 100.00);
    END IF;
END;
$$;

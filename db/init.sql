CREATE TABLE lecturas (
    id        BIGSERIAL PRIMARY KEY,
    sensor_id TEXT             NOT NULL,
    zona      TEXT             NOT NULL,
    valor     DOUBLE PRECISION NOT NULL,
    firma     TEXT             NOT NULL,
    ts        TIMESTAMPTZ      NOT NULL DEFAULT now()
);

CREATE INDEX idx_lecturas_zona_ts ON lecturas (zona, ts);

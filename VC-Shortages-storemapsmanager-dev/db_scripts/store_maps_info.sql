CREATE TABLE IF NOT EXISTS public.store_maps_info
(
    id uuid NOT NULL,
    location_id character varying COLLATE pg_catalog."default" NOT NULL,
    camera_friendly_name character varying COLLATE pg_catalog."default",
    section_info jsonb,
    create_ts timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT id PRIMARY KEY (id)
)

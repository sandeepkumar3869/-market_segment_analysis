CREATE TABLE IF NOT EXISTS public.store_maps
(
    section_id uuid NOT NULL,
    location_id VARCHAR NOT NULL,
	floor_id VARCHAR,
	section_name VARCHAR NOT NULL,
    coordinates POINT NULL,
	create_ts timestamp without time zone NOT NULL DEFAULT now(),
    camera_friendly_name VARCHAR,
    CONSTRAINT section_id PRIMARY KEY (section_id)
)
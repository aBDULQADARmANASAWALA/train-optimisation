```sql
create table stations (
    id uuid primary key default gen_random_uuid(),
    station_code varchar(10) unique not null,
    name varchar(255) not null,
    zone varchar(100),
    division varchar(100),
    latitude double precision,
    longitude double precision,
    total_platforms integer,
    created_at timestamp default now()
);
create table platforms (
    id uuid primary key default gen_random_uuid(),
    station_id uuid references stations(id) on delete cascade,
    platform_number integer not null,
    platform_length_meters integer,
    allowed_train_types varchar(100),
    is_active boolean default true,
    created_at timestamp default now(),
    unique (station_id, platform_number)
);
create table sections (
    id uuid primary key default gen_random_uuid(),
    from_station_id uuid references stations(id),
    to_station_id uuid references stations(id),
    distance_km numeric,
    travel_time_minutes integer,
    capacity integer not null,
    headway_minutes integer not null,
    signalling_type varchar(50),
    max_speed_kmph integer,
    gradient_profile text,
    is_bidirectional boolean default true,
    created_at timestamp default now()
);
create table maintenance_blocks (
    id uuid primary key default gen_random_uuid(),
    section_id uuid references sections(id),
    start_time timestamp not null,
    end_time timestamp not null,
    reason text,
    created_at timestamp default now()
);
create table trains (
    id uuid primary key default gen_random_uuid(),
    train_number varchar(20) unique not null,
    train_type varchar(50),
    priority_weight integer not null,
    max_speed_kmph integer,
    rake_length integer,
    created_at timestamp default now()
);
create table train_schedules (
    id uuid primary key default gen_random_uuid(),
    train_id uuid references trains(id) on delete cascade,
    station_id uuid references stations(id),
    scheduled_arrival timestamp,
    scheduled_departure timestamp,
    stop_order integer not null,
    platform_preference integer,
    created_at timestamp default now()
);
create table train_routes (
    id uuid primary key default gen_random_uuid(),
    train_id uuid references trains(id),
    section_id uuid references sections(id),
    sequence_order integer not null,
    created_at timestamp default now()
);
create table train_state (
    train_id uuid primary key references trains(id) on delete cascade,
    current_station_id uuid references stations(id),
    current_section_id uuid references sections(id),
    status varchar(50),
    actual_arrival timestamp,
    actual_departure timestamp,
    accumulated_delay_minutes integer default 0,
    last_updated timestamp default now()
);
create table section_occupancy (
    section_id uuid references sections(id),
    train_id uuid references trains(id),
    entry_time timestamp,
    expected_exit_time timestamp,
    primary key (section_id, train_id)
);
create table platform_occupancy (
    platform_id uuid references platforms(id),
    train_id uuid references trains(id),
    arrival_time timestamp,
    departure_time timestamp,
    primary key (platform_id, train_id)
);
create table optimization_runs (
    id uuid primary key default gen_random_uuid(),
    run_time timestamp default now(),
    horizon_start timestamp,
    horizon_end timestamp,
    objective_value numeric,
    total_weighted_delay numeric,
    solver_runtime_seconds numeric,
    status varchar(50)
);
create table optimized_schedule (
    id uuid primary key default gen_random_uuid(),
    optimization_run_id uuid references optimization_runs(id),
    train_id uuid references trains(id),
    station_id uuid references stations(id),
    optimized_arrival timestamp,
    optimized_departure timestamp,
    delay_minutes integer,
    precedence_rank integer,
    created_at timestamp default now()
);
create table precedence_decisions (
    id uuid primary key default gen_random_uuid(),
    optimization_run_id uuid references optimization_runs(id),
    train_a_id uuid references trains(id),
    train_b_id uuid references trains(id),
    section_id uuid references sections(id),
    decision varchar(50),
    created_at timestamp default now()
);
create table historical_operational_data (
    id uuid primary key default gen_random_uuid(),
    train_id uuid references trains(id),
    section_id uuid references sections(id),
    departure_delay integer,
    arrival_delay integer,
    section_load integer,
    time_of_day integer,
    congestion_flag boolean,
    created_at timestamp default now()
);
create table model_registry (
    id uuid primary key default gen_random_uuid(),
    model_name varchar(100),
    version varchar(50),
    trained_at timestamp,
    accuracy numeric,
    is_active boolean default true
);
create table kpi_metrics (
    id uuid primary key default gen_random_uuid(),
    timestamp timestamp default now(),
    total_weighted_delay numeric,
    average_delay numeric,
    throughput integer,
    section_utilization numeric
);
create table manual_overrides (
    id uuid primary key default gen_random_uuid(),
    train_id uuid references trains(id),
    section_id uuid references sections(id),
    overridden_decision text,
    reason text,
    overridden_by varchar(100),
    timestamp timestamp default now()
);
create index idx_train_state_section on train_state(current_section_id);
create index idx_schedule_train on train_schedules(train_id);
create index idx_section_from_to on sections(from_station_id, to_station_id);
create index idx_hist_train on historical_operational_data(train_id);
```
-- ==============================================================================
-- Migration 003: Idempotent Industrial Fleet Baseline Seed
-- Target: Supabase PostgreSQL
-- ==============================================================================

INSERT INTO machines (machine_id, name, machine_type, location, description, type_variant, status)
VALUES
    (
        'CNC-001',
        'Simulated CNC Milling Machine',
        'CNC Mill',
        'Bay 1 - Precision Milling Cell',
        '3-axis precision milling machine instrumented with AI4I physical telemetry sensors.',
        'M',
        'ONLINE'
    ),
    (
        'CNC-101',
        'Vertical CNC Milling Center 1',
        'CNC Mill',
        'Bay A - Precision Machining Cell',
        '5-axis vertical machining center for titanium aerostructure components.',
        'M',
        'ONLINE'
    ),
    (
        'PUMP-201',
        'High-Pressure Centrifugal Pump A',
        'Centrifugal Pump',
        'Utility Plant - Cooling Loop 2',
        'Variable-speed cooling fluid circulation pump rated for 350 GPM.',
        'L',
        'ONLINE'
    ),
    (
        'PRESS-301',
        'Hydraulic Stamping Press 300T',
        'Hydraulic Press',
        'Stamping Line 3',
        'Heavy duty 300-ton hydraulic sheet metal forming press.',
        'H',
        'ONLINE'
    ),
    (
        'COMP-401',
        'Rotary Screw Air Compressor B',
        'Air Compressor',
        'Compressor House 1',
        'Primary pneumatic supply rotary compressor operating at 7.5 bar nominal.',
        'M',
        'ONLINE'
    )
ON CONFLICT (machine_id) DO UPDATE SET
    name = EXCLUDED.name,
    machine_type = EXCLUDED.machine_type,
    location = EXCLUDED.location,
    description = EXCLUDED.description,
    type_variant = EXCLUDED.type_variant,
    status = EXCLUDED.status,
    updated_at = NOW();

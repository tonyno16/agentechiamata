-- ============================================================
-- SEED: Test Merchant + Product + Offers
-- Run in Supabase SQL Editor to enable WF-2 testing
-- ============================================================

-- Merchant
INSERT INTO merchants (id, name, affiliate_network, commission_type, commission_value, is_active)
VALUES (
    '11111111-1111-1111-1111-111111111111',
    'Test Merchant Italia',
    'direct',
    'CPA',
    25.00,
    true
)
ON CONFLICT (id) DO NOTHING;

-- Product: Vigor Gel (test)
INSERT INTO products (
    id, merchant_id, name, description, category,
    price, affiliate_link, landing_page_url, commission_per_sale, is_active
)
VALUES (
    '22222222-2222-2222-2222-222222222222',
    '11111111-1111-1111-1111-111111111111',
    'Vigor Gel',
    'Gel potenziante naturale a base di estratti vegetali. Formula avanzata per uomini che vogliono migliorare le loro prestazioni. Ingredienti: L-Arginina, Ginseng, Estratto di Maca. Applicazione: uso topico 30 minuti prima.',
    'adult',
    49.90,
    'https://example.com/vigor-gel',
    'https://vigorgel.it',
    25.00,
    true
)
ON CONFLICT (id) DO NOTHING;

-- Offers: 1x / 2x / 3x bundle
INSERT INTO offers (id, product_id, name, description, discount_type, discount_value, is_active)
VALUES
    (
        '33333333-3333-3333-3333-333333333301',
        '22222222-2222-2222-2222-222222222222',
        'Confezione Base – 1 flacone',
        '1 flacone da 50ml. Prezzo pieno. Spedizione gratuita.',
        'fixed',
        0,
        true
    ),
    (
        '33333333-3333-3333-3333-333333333302',
        '22222222-2222-2222-2222-222222222222',
        'Confezione Doppia – 2 flaconi',
        '2 flaconi da 50ml. Risparmio del 15%. Trattamento completo 60 giorni.',
        'percentage',
        15,
        true
    ),
    (
        '33333333-3333-3333-3333-333333333303',
        '22222222-2222-2222-2222-222222222222',
        'Confezione Famiglia – 3 flaconi',
        '3 flaconi da 50ml. Risparmio del 25%. Trattamento completo 90 giorni. Più venduto.',
        'percentage',
        25,
        true
    )
ON CONFLICT (id) DO NOTHING;

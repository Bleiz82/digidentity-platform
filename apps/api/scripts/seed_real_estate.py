"""
Seed script per il pack real-estate-luxury.
Inserisce 100 entità immobiliari su 3 tenant fittizi.
Idempotente: usa slug univoco nel payload, skip se già presente.
Stub embeddings — nessuna chiamata API reale.

Uso diretto (richiede DATABASE_URL in env):
    cd apps/api && uv run python scripts/seed_real_estate.py

Uso programmatico (per test):
    from scripts.seed_real_estate import seed_database
    await seed_database(session_factory, tenant_ids)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import UUID

import uuid_utils
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from digidentity_api.db.models import Entity, Tenant
from digidentity_api.db.tenant_context import with_tenant
from digidentity_api.packs.stub_embeddings import make_stub_embedding
from digidentity_api.packs.templates import render_pack_templates

PACK_ROOT = Path(__file__).parent.parent.parent.parent / "packs" / "real-estate-luxury"
PACK_ID = "real-estate-luxury"

# 100 proprietà sintetiche ma realistiche
PROPERTIES: list[dict] = [
    {
        "title": "Villa Asfodelo",
        "property_type": "villa",
        "location": "Porto Cervo, Costa Smeralda",
        "description": "Villa esclusiva con panorama sul mare, immersa nella macchia mediterranea.",
        "price": 4500000,
        "rooms": 6,
        "bathrooms": 5,
        "sqm": 420,
        "land_sqm": 3000,
        "pool": True,
        "pool_type": "infinity",
        "garage": 2,
        "elevator": False,
        "sea_distance": 150,
        "year_built": 2018,
        "energy_class": "A",
        "lifestyle_tags": ["mare", "exclusivita", "design"],
        "lifestyle_narrative": "Mattine in piscina infinity con vista sul golfo, cene sulla terrazza al tramonto. Porto Cervo a 5 minuti.",
        "location_lifestyle": "Il cuore della Costa Smeralda, circondato da boutique di lusso e ristoranti stellati.",
        "outdoor_spaces": ["terrazza panoramica", "giardino privato", "piscina infinity"],
        "wellness": ["sauna", "zona relax bordo piscina"],
        "features": ["vista mare", "piscina infinity", "domotica"],
        "slug": "villa-asfodelo-porto-cervo",
    },
    {
        "title": "Residenza Ginepro",
        "property_type": "villa",
        "location": "Porto Rotondo, Sardegna",
        "description": "Residenza d'autore con finiture di pregio, a pochi passi dal porto turistico.",
        "price": 3200000,
        "rooms": 5,
        "bathrooms": 4,
        "sqm": 380,
        "land_sqm": 2500,
        "pool": True,
        "pool_type": "riscaldata",
        "garage": 2,
        "elevator": False,
        "sea_distance": 300,
        "year_built": 2015,
        "energy_class": "A",
        "lifestyle_tags": ["porto", "sailing", "family"],
        "lifestyle_narrative": "Aperitivi sul porto, regate del mercoledì, cene di pesce fresco. La vita come dovrebbe essere.",
        "location_lifestyle": "Porto Rotondo: il porto dei velisti, la quiete dei palazzi, il calore dei sardi.",
        "outdoor_spaces": ["veranda coperta", "piscina riscaldata", "giardino fiorito"],
        "wellness": ["idromassaggio", "palestra privata"],
        "features": ["vista porto", "finiture artigianali", "cantina vini"],
        "slug": "residenza-ginepro-porto-rotondo",
    },
    {
        "title": "Attico Duomo",
        "property_type": "attico",
        "location": "Milano, Quadrilatero della Moda",
        "description": "Attico di design con terrazza esclusiva, nel cuore del quadrilatero della moda.",
        "price": 5800000,
        "rooms": 4,
        "bathrooms": 3,
        "sqm": 280,
        "land_sqm": 120,
        "pool": False,
        "pool_type": None,
        "garage": 1,
        "elevator": True,
        "sea_distance": None,
        "year_built": 2020,
        "energy_class": "A+",
        "lifestyle_tags": ["design", "fashion", "aperitivo"],
        "lifestyle_narrative": "Colazione con vista sui tetti del Duomo, shopping a via Montenapoleone, aperitivo in terrazza. Milano come pochi la vivono.",
        "location_lifestyle": "Via della Spiga a 200 metri. Armani, Prada, Bulgari sotto casa.",
        "outdoor_spaces": ["terrazza esclusiva 80mq", "loggia living"],
        "wellness": ["spa condominiale", "palestra condominiale"],
        "features": ["vista Duomo", "terrazza 80mq", "domotica Lutron"],
        "slug": "attico-duomo-quadrilatero",
    },
    {
        "title": "Villa dei Cipressi",
        "property_type": "villa",
        "location": "Fiesole, Firenze",
        "description": "Villa storica con parco secolare, vista panoramica su Firenze. Affreschi originali, cantina.",
        "price": 7200000,
        "rooms": 8,
        "bathrooms": 6,
        "sqm": 650,
        "land_sqm": 15000,
        "pool": True,
        "pool_type": "classica",
        "garage": 4,
        "elevator": True,
        "sea_distance": None,
        "year_built": 1890,
        "energy_class": "D",
        "lifestyle_tags": ["storia", "arte", "toscana"],
        "lifestyle_narrative": "Passeggiare tra i cipressi all'alba, visitare il Duomo a 20 minuti, degustare Chianti dalla propria cantina.",
        "location_lifestyle": "Fiesole domina Firenze. Vista Brunelleschi dalla piscina.",
        "outdoor_spaces": ["parco 15.000 mq", "limonaia", "piscina con solarium"],
        "wellness": ["spa storica", "campo da tennis"],
        "features": ["affreschi originali", "cantina storica", "limonaia"],
        "slug": "villa-dei-cipressi-fiesole",
    },
    {
        "title": "Chalet Grand View",
        "property_type": "chalet",
        "location": "Cortina d'Ampezzo, Dolomiti",
        "description": "Chalet di montagna con spa privata, direttamente sulle piste. Materiali naturali e design alpino di lusso.",
        "price": 6500000,
        "rooms": 7,
        "bathrooms": 6,
        "sqm": 550,
        "land_sqm": 1800,
        "pool": False,
        "pool_type": None,
        "garage": 3,
        "elevator": False,
        "sea_distance": None,
        "year_built": 2019,
        "energy_class": "A",
        "lifestyle_tags": ["sci", "montagna", "wellness"],
        "lifestyle_narrative": "Sci fino alla porta, aperski al rifugio, rientro nella propria spa. Dolomiti Patrimonio UNESCO fuori dalla finestra.",
        "location_lifestyle": "Cortina: mondanità alpina, il meglio dell'inverno italiano.",
        "outdoor_spaces": ["terrazza panoramica Dolomiti", "giardino alpino", "area ski room"],
        "wellness": ["spa privata", "sauna finlandese", "piscina coperta riscaldata"],
        "features": ["ski in ski out", "spa privata", "cantina"],
        "slug": "chalet-grand-view-cortina",
    },
    {
        "title": "Masseria Ulivi d'Oro",
        "property_type": "masseria",
        "location": "Fasano, Valle d'Itria, Puglia",
        "description": "Masseria del '700 completamente ristrutturata con piscina, oliveto, trulli ospiti.",
        "price": 2800000,
        "rooms": 9,
        "bathrooms": 7,
        "sqm": 700,
        "land_sqm": 80000,
        "pool": True,
        "pool_type": "naturale",
        "garage": 5,
        "elevator": False,
        "sea_distance": 8000,
        "year_built": 1740,
        "energy_class": "E",
        "lifestyle_tags": ["puglia", "slow_life", "trulli"],
        "lifestyle_narrative": "Raccolta delle olive a ottobre, cene sotto il pergolato, visite ai trulli di Alberobello. Il Sud come non si vede nei film.",
        "location_lifestyle": "Valle d'Itria: paesaggi da cartolina, cucina casereccia, ostuni bianca a 15 minuti.",
        "outdoor_spaces": ["oliveto 3 ettari", "piscina naturale", "4 trulli ospiti"],
        "wellness": ["bagno turco", "yoga pavilion"],
        "features": ["oliveto produttivo", "trulli storici", "cantina botti"],
        "slug": "masseria-ulivi-doro-fasano",
    },
    {
        "title": "Penthouse Lake Como",
        "property_type": "penthouse",
        "location": "Bellagio, Lago di Como",
        "description": "Penthouse sul lago di Como con terrazza privata e pontile. Design contemporaneo, vista mozzafiato.",
        "price": 8900000,
        "rooms": 5,
        "bathrooms": 4,
        "sqm": 450,
        "land_sqm": 200,
        "pool": True,
        "pool_type": "terrazza",
        "garage": 2,
        "elevator": True,
        "sea_distance": 0,
        "year_built": 2022,
        "energy_class": "A+",
        "lifestyle_tags": ["lago", "celebrity", "sailing"],
        "lifestyle_narrative": "Svegliarsi sul lago, prendere l'hydrofoil per Como, cena a Villa d'Este. Bellagio: l'indirizzo più famoso d'Italia.",
        "location_lifestyle": "Bellagio divide il lago. Clooney è vicino di casa.",
        "outdoor_spaces": ["terrazza 200mq con piscina", "pontile privato"],
        "wellness": ["palestra panoramica", "vasca idromassaggio sul lago"],
        "features": ["pontile privato", "terrazza piscina", "barca inclusa"],
        "slug": "penthouse-lake-como-bellagio",
    },
    {
        "title": "Villa Marina Grande",
        "property_type": "villa",
        "location": "Positano, Costiera Amalfitana",
        "description": "Villa d'autore aggrappata alla roccia di Positano, con piscina a sfioro e accesso privato al mare.",
        "price": 9500000,
        "rooms": 6,
        "bathrooms": 5,
        "sqm": 380,
        "land_sqm": 800,
        "pool": True,
        "pool_type": "sfioro sul mare",
        "garage": 0,
        "elevator": True,
        "sea_distance": 0,
        "year_built": 2010,
        "energy_class": "B",
        "lifestyle_tags": ["costiera", "mare", "dolce_vita"],
        "lifestyle_narrative": "Colazione sulla terrazza con vista Positano, bagno privato al mare, aperitivo al tramonto rosa. La costiera come pochissimi la vivono.",
        "location_lifestyle": "Positano: scalinate, profumo di limoni, barche bianche. Napoli a 1 ora.",
        "outdoor_spaces": ["terrazza panoramica", "piscina sfioro", "accesso mare privato"],
        "wellness": ["hammam", "zona massaggi vista mare"],
        "features": ["accesso mare privato", "piscina sfioro sul mare", "ascensore interno"],
        "slug": "villa-marina-grande-positano",
    },
    {
        "title": "Palazzo Venezia",
        "property_type": "palazzo",
        "location": "Venezia, Dorsoduro",
        "description": "Palazzo del '500 sul Canal Grande, Dorsoduro. Piano nobile con affreschi, molo privato.",
        "price": 12000000,
        "rooms": 10,
        "bathrooms": 8,
        "sqm": 900,
        "land_sqm": 400,
        "pool": False,
        "pool_type": None,
        "garage": 0,
        "elevator": False,
        "sea_distance": 0,
        "year_built": 1520,
        "energy_class": "G",
        "lifestyle_tags": ["venezia", "storia", "arte"],
        "lifestyle_narrative": "Gondola di mattina, Biennale a settembre, aperitivo al tramonto sul molo di casa. Venezia come i veneziani del '500.",
        "location_lifestyle": "Dorsoduro: gallerie d'arte, bar da locals, Canal Grande sotto casa.",
        "outdoor_spaces": ["molo privato", "cortile interno", "altana panoramica"],
        "wellness": ["bagno turco", "sala fitness"],
        "features": ["molo privato", "affreschi originali", "piano nobile"],
        "slug": "palazzo-venezia-dorsoduro",
    },
    {
        "title": "Casale Il Sasso",
        "property_type": "casale",
        "location": "Montalcino, Val d'Orcia, Toscana",
        "description": "Casale toscano con vigna Brunello di Montalcino DOC, cantina e dependance.",
        "price": 3800000,
        "rooms": 7,
        "bathrooms": 5,
        "sqm": 520,
        "land_sqm": 120000,
        "pool": True,
        "pool_type": "classica",
        "garage": 3,
        "elevator": False,
        "sea_distance": None,
        "year_built": 1650,
        "energy_class": "F",
        "lifestyle_tags": ["vino", "toscana", "agriturismo"],
        "lifestyle_narrative": "Vendemmia a settembre, assaggi in cantina, pic-nic nella vigna con vista sulla Val d'Orcia. Il Brunello è di casa.",
        "location_lifestyle": "Montalcino: il Brunello, i cipressi, il silenzio. UNESCO a pochi km.",
        "outdoor_spaces": ["vigna 8 ettari", "piscina panoramica", "loggia"],
        "wellness": ["sauna in cantina", "area meditazione"],
        "features": ["vigna Brunello DOC", "cantina produttiva", "dependance"],
        "slug": "casale-il-sasso-montalcino",
    },
]

# Estendi a 100 proprietà aggiungendo varianti con location diverse
_LOCATIONS_EXTRA = [
    ("Capri, Napoli", "capri"), ("Taormina, Sicilia", "taormina"),
    ("Forte dei Marmi, Versilia", "forte-dei-marmi"), ("Porto Ercole, Argentario", "porto-ercole"),
    ("Ravello, Costiera Amalfitana", "ravello"), ("Stresa, Lago Maggiore", "stresa"),
    ("Portofino, Liguria", "portofino"), ("Alassio, Riviera Ligure", "alassio"),
    ("Gardone Riviera, Lago di Garda", "gardone"), ("Madonna di Campiglio, Trentino", "campiglio"),
    ("Courmayeur, Valle d'Aosta", "courmayeur"), ("Sestriere, Piemonte", "sestriere"),
    ("Ortisei, Alto Adige", "ortisei"), ("Merano, Alto Adige", "merano"),
    ("Castelfidardo, Marche", "castelfidardo"), ("Sperlonga, Lazio", "sperlonga"),
    ("Sabaudia, Lazio", "sabaudia"), ("Otranto, Puglia", "otranto"),
    ("Tropea, Calabria", "tropea"), ("Erice, Sicilia", "erice"),
    ("Ragusa Ibla, Sicilia", "ragusa"), ("Noto, Sicilia", "noto"),
    ("Marsala, Sicilia", "marsala"), ("Pantelleria, Sicilia", "pantelleria"),
    ("Stromboli, Eolie", "stromboli"), ("Salina, Eolie", "salina"),
    ("Ischia, Napoli", "ischia"), ("Procida, Napoli", "procida"),
    ("Lipari, Eolie", "lipari"), ("Giardini Naxos, Sicilia", "giardini-naxos"),
    ("Siracusa, Sicilia", "siracusa"), ("Agrigento, Sicilia", "agrigento"),
    ("Palermo, Sicilia", "palermo"), ("Mondello, Sicilia", "mondello"),
    ("Cefalù, Sicilia", "cefalu"), ("Scopello, Sicilia", "scopello"),
    ("San Vito Lo Capo, Sicilia", "san-vito"), ("Castellammare del Golfo", "castellammare"),
    ("Marzamemi, Sicilia", "marzamemi"), ("Sampieri, Sicilia", "sampieri"),
    ("Bari Vecchia, Puglia", "bari-vecchia"), ("Polignano a Mare, Puglia", "polignano"),
    ("Monopoli, Puglia", "monopoli"), ("Alberobello, Puglia", "alberobello"),
    ("Ostuni, Puglia", "ostuni"), ("Locorotondo, Puglia", "locorotondo"),
    ("Matera, Basilicata", "matera"), ("Maratea, Basilicata", "maratea"),
    ("Scilla, Calabria", "scilla"), ("Pizzo Calabro, Calabria", "pizzo"),
    ("Vietri sul Mare, Campania", "vietri"), ("Amalfi, Campania", "amalfi"),
    ("Palinuro, Campania", "palinuro"), ("Agropoli, Campania", "agropoli"),
    ("Santa Margherita Ligure, Liguria", "santa-margherita"), ("Chiavari, Liguria", "chiavari"),
    ("Camogli, Liguria", "camogli"), ("Levanto, Liguria", "levanto"),
    ("Lerici, Liguria", "lerici"), ("La Spezia, Liguria", "la-spezia"),
    ("Sestri Levante, Liguria", "sestri"), ("Bordighera, Liguria", "bordighera"),
    ("Sanremo, Liguria", "sanremo"), ("Ventimiglia, Liguria", "ventimiglia"),
    ("Bellagio (villetta), Lago Como", "bellagio-villetta"), ("Varenna, Lago Como", "varenna"),
    ("Menaggio, Lago Como", "menaggio"), ("Tremezzo, Lago Como", "tremezzo"),
    ("Laveno, Lago Maggiore", "laveno"), ("Verbania, Lago Maggiore", "verbania"),
    ("Pallanza, Lago Maggiore", "pallanza"), ("Baveno, Lago Maggiore", "baveno"),
    ("Garda, Lago di Garda", "garda"), ("Lazise, Lago di Garda", "lazise"),
    ("Malcesine, Lago di Garda", "malcesine"), ("Sirmione, Lago di Garda", "sirmione"),
    ("Riva del Garda, Trentino", "riva-del-garda"), ("Arco, Trentino", "arco"),
    ("Trento, Trentino", "trento"), ("Rovereto, Trentino", "rovereto"),
    ("Asiago, Veneto", "asiago"), ("Cortina (chalet 2), Dolomiti", "cortina-2"),
    ("Alta Badia, Alto Adige", "alta-badia"), ("Val Gardena, Alto Adige", "val-gardena"),
    ("Bressanone, Alto Adige", "bressanone"), ("Bolzano, Alto Adige", "bolzano"),
    ("Aosta, Valle d'Aosta", "aosta"), ("Gressoney, Valle d'Aosta", "gressoney"),
    ("Cogne, Valle d'Aosta", "cogne"), ("Cervinia, Valle d'Aosta", "cervinia"),
]


def _build_extra_property(i: int, location: str, slug_suffix: str) -> dict:
    types = ["villa", "attico", "casale", "chalet", "residenza", "masseria"]
    rooms_range = [3, 4, 5, 6, 7, 8]
    base_price = 800000 + (i * 87000)
    return {
        "title": f"Proprietà {slug_suffix.replace('-', ' ').title()}",
        "property_type": types[i % len(types)],
        "location": location,
        "description": f"Proprietà di pregio a {location.split(',')[0]}, finiture di alto livello.",
        "price": base_price,
        "rooms": rooms_range[i % len(rooms_range)],
        "bathrooms": max(2, rooms_range[i % len(rooms_range)] - 2),
        "sqm": 150 + (i * 23) % 500,
        "land_sqm": 500 + (i * 150) % 5000,
        "pool": i % 3 != 0,
        "pool_type": "classica" if i % 3 != 0 else None,
        "garage": i % 4,
        "elevator": i % 5 == 0,
        "sea_distance": (i * 137) % 2000 if i % 4 != 0 else None,
        "year_built": 1900 + (i * 7) % 123,
        "energy_class": ["A", "A+", "B", "C", "D"][i % 5],
        "lifestyle_tags": ["mare", "montagna", "lago", "campagna", "città"][i % 5 : i % 5 + 2],
        "lifestyle_narrative": f"La vita a {location.split(',')[0]}: semplicità e bellezza.",
        "location_lifestyle": f"{location}: paesaggi unici e qualità della vita eccellente.",
        "outdoor_spaces": ["terrazza", "giardino"] if i % 2 == 0 else ["balcone"],
        "wellness": ["sauna"] if i % 3 == 0 else [],
        "features": ["vista panoramica", f"{150 + (i * 23) % 500} mq"],
        "slug": f"property-{slug_suffix}-{i}",
    }


ALL_PROPERTIES: list[dict] = PROPERTIES + [
    _build_extra_property(i, loc, slug)
    for i, (loc, slug) in enumerate(_LOCATIONS_EXTRA[:90])
]
# Esattamente 100
ALL_PROPERTIES = ALL_PROPERTIES[:100]


async def seed_database(
    session_factory: async_sessionmaker,
    tenant_ids: list[UUID],
) -> dict[str, int]:
    """
    Inserisce le 100 entità su ogni tenant.
    Idempotente: skippa se slug già presente nel payload.
    Ritorna {tenant_id_str: inserted_count}.
    """
    results: dict[str, int] = {}
    for i, tid in enumerate(tenant_ids):
        inserted = 0
        # Crea tenant se non esiste
        async with with_tenant(tid, session_factory=session_factory) as sess:
            existing_tenant = await sess.get(Tenant, tid)
            if not existing_tenant:
                tenant = Tenant(
                    id=tid,
                    slug=f"seed-tenant-{i}",
                    name=f"Seed Tenant {i} (real-estate-luxury)",
                )
                sess.add(tenant)

        for prop_data in ALL_PROPERTIES:
            async with with_tenant(tid, session_factory=session_factory) as sess:
                # Idempotency check: cerca slug nel payload
                existing = await sess.execute(
                    sa_text(
                        "SELECT id FROM entities WHERE tenant_id = :tid "
                        "AND payload->>'slug' = :slug LIMIT 1"
                    ),
                    {"tid": str(tid), "slug": prop_data["slug"]},
                )
                if existing.fetchone():
                    continue

                # Renderizza templates
                rendered = render_pack_templates(PACK_ROOT, prop_data)
                content_text = rendered.get("content_template", "")
                lifestyle_text = rendered.get("lifestyle_template", "")
                features_text = rendered.get("features_template", "")

                entity = Entity(
                    tenant_id=tid,
                    pack_id=PACK_ID,
                    entity_type="property",
                    payload=prop_data,
                    content_emb=make_stub_embedding(content_text or str(prop_data), "content"),
                    lifestyle_emb=make_stub_embedding(lifestyle_text or str(prop_data), "lifestyle"),
                    features_emb=make_stub_embedding(features_text or str(prop_data), "features"),
                    embedding_version="text-embedding-3-large-halfvec-v1",
                )
                sess.add(entity)
                inserted += 1

        results[str(tid)] = inserted

    return results


if __name__ == "__main__":
    import os
    from sqlalchemy.ext.asyncio import create_async_engine

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL env var required")
        sys.exit(1)

    engine = create_async_engine(db_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    tenant_ids_env = os.environ.get("SEED_TENANT_IDS", "")
    if tenant_ids_env:
        tids = [UUID(x.strip()) for x in tenant_ids_env.split(",")]
    else:
        # 3 tenant fissi per dev locale
        tids = [
            UUID("00000000-0000-0000-0000-000000000001"),
            UUID("00000000-0000-0000-0000-000000000002"),
            UUID("00000000-0000-0000-0000-000000000003"),
        ]

    counts = asyncio.run(seed_database(factory, tids))
    for tid_str, count in counts.items():
        print(f"Tenant {tid_str}: {count} entità inserite")

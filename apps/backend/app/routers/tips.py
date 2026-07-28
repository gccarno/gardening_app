"""
Tip of the Day -- one tip per day, chosen by the ordinal day number.

This used to run through a ChromaDB collection, which cost the app two
production outages (2026-07-27 and 2026-07-28): the first request after a cold
start made Chroma download and load its default embedding model
(all-MiniLM-L6-v2, 79 MB) inside the web process, and the load OOM-killed the
512 MB Render instance for ~60-90s. Render's disk is ephemeral, so it happened
on every cold start.

Nothing was gained for that price. The collection was seeded from and only ever
contained _SEED_TIPS, `garden_tips` was referenced nowhere else, and the
endpoint never ran a similarity query -- it fetched every document and indexed
by date, which is exactly what it does now without the vector store.
"""
from datetime import date

from fastapi import APIRouter

router = APIRouter(prefix='/api', tags=['tips'])

_SEED_TIPS = [
    "Water deeply and infrequently. Shallow, frequent watering encourages roots to stay near the surface. Deep watering once or twice a week pushes roots down where soil stays moist longer.",
    "Add a 2-3 inch layer of mulch around plants to retain moisture, suppress weeds, and regulate soil temperature. Keep mulch a few inches away from plant stems to prevent rot.",
    "Tomatoes love consistent moisture. Irregular watering causes blossom end rot and fruit cracking. Use a soaker hose or drip irrigation to keep soil evenly moist.",
    "Test your soil pH before planting. Most vegetables thrive in slightly acidic soil (6.0-7.0). A $10 soil test kit from a garden center can save a whole season of poor growth.",
    "Plant basil near tomatoes to repel aphids and whiteflies and improve flavor. This classic companion planting combination has been used by gardeners for centuries.",
    "Never till wet soil. Working compacted, wet soil destroys its structure and creates dense clods that roots struggle to penetrate. Wait until a handful of soil crumbles when squeezed.",
    "Pinch off the first flower buds on pepper and eggplant transplants. This redirects energy to root and stem growth, leading to larger, more productive plants later in the season.",
    "Harvest zucchini when it is 6-8 inches long. Left to grow, it quickly becomes tough and seedy -- and slows production. Check your zucchini plants every day during peak season.",
    "Start seeds in trays 6-8 weeks before your last frost date. Harden off seedlings over 7-10 days by gradually exposing them to outdoor conditions before transplanting.",
    "Companion plant marigolds throughout the vegetable garden. Their roots produce a compound that deters nematodes, and their flowers attract beneficial predatory insects.",
    "Deadhead flowering plants regularly to extend the bloom period. Removing spent flowers signals the plant to produce more blooms rather than setting seed.",
    "Rotate your crops each season. Growing the same family of plants in the same bed year after year depletes specific nutrients and allows pests and diseases to build up in the soil.",
    "Water in the morning, not the evening. Morning watering lets foliage dry during the day, reducing the risk of fungal diseases like powdery mildew and black spot.",
    "Add compost to your beds every season. A 2-inch layer worked into the top 6 inches of soil improves drainage in clay soils, increases water retention in sandy soils, and feeds soil life.",
    "Garlic planted near roses repels aphids. Plant a ring of garlic cloves around rose bushes in fall for natural pest protection the following season.",
    "Thin seedlings ruthlessly. Overcrowded plants compete for light, water, and nutrients -- and produce less than properly spaced plants. It feels wasteful, but thinning is essential.",
    "Keep a garden journal. Record what you planted, when, and how it performed. Notes from past seasons are the most valuable resource for improving next year's garden.",
    "Use the 'finger test' before watering. Insert a finger 2 inches into the soil -- if it feels moist, hold off. Most plants prefer to dry out slightly between waterings.",
    "Plant dill near cabbage to attract beneficial wasps that parasitize cabbage worms. Avoid planting dill near carrots, which it can inhibit.",
    "Succession plant fast-growing crops like lettuce, radishes, and beans every 2-3 weeks. This gives you a continuous harvest instead of a glut followed by nothing.",
    "Feed heavy-feeding vegetables like tomatoes, peppers, and corn with a balanced fertilizer every 2-3 weeks during the growing season. Switch to a low-nitrogen formula once flowering begins.",
    "Store seeds in a cool, dry, dark place -- ideally in an airtight container with a silica gel packet. Properly stored seeds can remain viable for 3-5 years.",
    "Epsom salt (magnesium sulfate) can treat magnesium deficiency, which shows up as yellowing between leaf veins on older leaves. Dissolve 1 tablespoon per gallon of water and apply to soil.",
    "Plant nasturtiums as a trap crop for aphids. Aphids cluster on nasturtiums rather than your vegetables, where they can be hosed off or left for beneficial insects.",
    "Avoid walking on garden beds. Foot traffic compacts soil, reducing pore space and limiting root growth. Design beds narrow enough (4 ft max) to reach the center from either side.",
    "Neem oil spray controls a wide range of soft-bodied insects (aphids, mites, whiteflies) and fungal diseases. Apply in the evening to avoid burning foliage in direct sunlight.",
    "Save seeds from open-pollinated (non-hybrid) varieties to grow next year. Let the best fruits fully mature on the plant before harvesting seeds, then dry them thoroughly before storage.",
    "Interplant shallow-rooted crops like lettuce and radishes with deep-rooted crops like tomatoes or peppers. They occupy different soil layers and don't compete for the same resources.",
    "Cover brassicas (cabbage, broccoli, kale) with floating row cover immediately after transplanting to exclude cabbage butterflies before they can lay eggs.",
    "Fertilize container plants more frequently than in-ground plants. Frequent watering leaches nutrients from potting mix. Feed container plants with a diluted balanced fertilizer every 1-2 weeks.",
    "When transplanting, always water the hole before inserting the plant. This eliminates air pockets around roots and ensures immediate contact between roots and moist soil.",
    "Cut herbs like basil, mint, and oregano just above a leaf node to encourage bushy growth. Never remove more than one-third of the plant at a time.",
    "Beans fix atmospheric nitrogen in the soil through a symbiosis with soil bacteria. After harvest, cut bean plants at ground level and leave the roots to decompose -- they release nitrogen into the soil.",
    "Ladybugs, lacewings, and parasitic wasps are your garden allies. Avoid broad-spectrum pesticides that kill beneficial insects. Target sprays precisely and prefer organic options.",
    "Build a compost pile with equal parts 'greens' (kitchen scraps, fresh grass clippings) and 'browns' (dry leaves, cardboard, straw). Turn it weekly and keep it as moist as a wrung-out sponge.",
    "Stake tomatoes early -- don't wait until they start falling over. Driving a stake next to a large plant risks damaging roots. Use cages, stakes, or a trellis installed at planting time.",
    "Prune suckers from indeterminate tomato varieties (a shoot that grows from the junction of the stem and a branch). This focuses energy into fewer, larger fruits instead of excessive foliage.",
    "Plant cover crops like clover, buckwheat, or winter rye in empty beds to protect soil from erosion, suppress weeds, and improve fertility. Till or cut them down before they set seed.",
    "Check the undersides of leaves regularly for pest eggs and early infestations. Many pests -- aphids, spider mites, whitefly -- concentrate on the leaf underside and are easiest to control early.",
    "Hot peppers and cold temperatures are linked: the capsaicin compound that causes heat is produced as a stress response. Slightly water-stressed plants often produce hotter fruit.",
    "Harvest lettuce in the cool of the morning, when leaves are crisp and fully hydrated. Lettuce picked in afternoon heat wilts quickly even after refrigeration.",
    "Sow carrots directly in the garden -- they don't transplant well. Sow thinly in well-loosened soil free of rocks. Cover seeds lightly and keep the surface consistently moist until germination.",
    "Use a cold frame to extend the growing season by 4-6 weeks in spring and fall. Even a simple frame of old windows propped over a low bed can make a big difference.",
    "Bees and pollinators are most active in warm, sunny conditions. Schedule any spraying (even organic sprays) for late evening when pollinators have returned to their nests.",
    "Add worm castings to seed-starting mix or transplant holes. Worm castings are rich in plant-available nutrients and beneficial microbes that suppress soil-borne diseases.",
    "Herbs grown for their leaves -- basil, cilantro, parsley -- should be harvested before they flower (bolt). Once a plant flowers and sets seed, leaf quality and production drop significantly.",
    "Clip garlic scapes (the curling flower stalks) from hardneck garlic in early summer. This redirects energy to the bulb, increasing bulb size significantly.",
    "Keep garden tools clean and sharp. A sharp hoe slices weeds at the soil line with minimal effort. Wipe metal parts with an oily rag after use to prevent rust.",
    "Plant sunflowers on the north side of the garden so they don't shade shorter crops. Their tall stalks also serve as a natural trellis for climbing beans.",
    "Soak large seeds (beans, corn, peas, squash) in water for 8-12 hours before planting. This softens the seed coat and speeds germination by several days.",
    "Use drip irrigation or soaker hoses instead of overhead watering in the vegetable garden. Keeping foliage dry reduces disease pressure, especially in humid climates.",
    "Raised beds warm up faster in spring, drain better, and can be managed without walking on the soil. Fill with a mixture of topsoil, compost, and a small amount of perlite for excellent drainage.",
    "Pinch back annual herbs like basil immediately when you see flower buds forming. Once basil blooms, the leaves become smaller and more bitter. Regular pinching delays bolting by weeks.",
    "Monitor for cucumber beetles in spring -- they spread bacterial wilt. Row cover early in the season excludes them. Remove cover when plants flower so bees can pollinate.",
    "Don't over-fertilize with nitrogen late in the season. High nitrogen promotes leafy growth at the expense of fruit production and makes plants more susceptible to fungal disease and frost damage.",
    "Harvest garlic when about half the leaves have turned brown (usually midsummer). Pull bulbs and cure in a warm, dry, well-ventilated spot for 3-4 weeks before storing.",
    "Use a spray bottle of diluted dish soap (a few drops per quart of water) to knock out small aphid infestations quickly. Repeat every 2-3 days for a week to break the cycle.",
    "Plant strawberries in a new location every 3-4 years. Old strawberry beds accumulate diseases and the plants become less productive. Start fresh with certified disease-free runners.",
    "Feed roses with a fertilizer formulated for roses (slightly higher phosphorus and potassium than nitrogen) every 4-6 weeks from first leaf break until 6 weeks before the first expected frost.",
    "Side-dress heavy feeders like corn, squash, and melons with compost or balanced granular fertilizer when they are knee-high. Work it into the top inch of soil around (not against) the stem.",
    "Mark your planting dates on stakes or in your garden journal. Knowing exactly when you planted lets you calculate days to harvest, monitor for potential disease, and plan succession plantings.",
    "Remove and dispose of diseased plant material -- don't compost it. Fungal spores and bacterial pathogens can survive in compost that doesn't reach high enough temperatures to kill them.",
    "Grow vertically to save space. Cucumbers, pole beans, and melons all thrive on a trellis. Vertical growing improves air circulation, reduces disease, and makes harvesting easier.",
    "Pepper plants grown in slightly crowded conditions (12 inches apart vs. 18) often produce earlier and more abundantly because the plants shade each other and reduce soil moisture loss.",
]


@router.get('/tip-of-the-day')
def tip_of_the_day():
    idx = date.today().toordinal() % len(_SEED_TIPS)
    return {'tip': _SEED_TIPS[idx], 'tip_index': idx, 'total': len(_SEED_TIPS)}

"""species_key is the label unit for plant ID — cultivars must pool into their taxon."""
import pytest

from ml.features.plantid_data import species_key


@pytest.mark.parametrize('raw, expected', [
    ('Capsicum annuum', 'capsicum annuum'),
    ('  Capsicum   annuum ', 'capsicum annuum'),
    ('Solanum lycopersicum (Brandywine)', 'solanum lycopersicum'),
    ("Capsicum annuum 'Jalapeno'", 'capsicum annuum'),
    ('Capsicum annuum ‘Cayenne’', 'capsicum annuum'),
    ('Brassica oleracea var. capitata', 'brassica oleracea capitata'),
    ('Brassica oleracea capitata', 'brassica oleracea capitata'),
    ('Lathyrus japonicus subsp. maritimus', 'lathyrus japonicus maritimus'),
    ('Dianthus x hybrida', 'dianthus x hybrida'),
])
def test_species_key(raw, expected):
    assert species_key(raw) == expected

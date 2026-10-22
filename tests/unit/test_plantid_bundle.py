"""load_bundle reads a Colab bundle with no DB — what training/export use off-machine."""
import json

import numpy as np
from PIL import Image

from ml.features.plantid_data import load_bundle


def _fixture_bundle(root):
    classes = [
        {'species_key': 'capsicum annuum', 'scientific_name': 'Capsicum annuum', 'plant_library_id': 7, 'n_images': 3},
        {'species_key': 'solanum lycopersicum', 'scientific_name': 'Solanum lycopersicum', 'plant_library_id': 1, 'n_images': 2},
    ]
    (root / 'classes.json').write_text(json.dumps(classes), encoding='utf-8')
    (root / 'meta.json').write_text(json.dumps({'alpha': 0.0}), encoding='utf-8')
    np.save(root / 'teacher_protos.npy', np.eye(2, 4, dtype=np.float32))
    np.save(root / 'teacher_text.npy', np.eye(2, 4, dtype=np.float32))
    (root / 'eval').mkdir()
    Image.new('RGB', (8, 8)).save(root / 'eval' / '11.jpg')
    (root / 'eval.csv').write_text(
        'species_key,scientific_name,path,is_crop\n'
        'capsicum annuum,Capsicum annuum,eval/11.jpg,1\n'
        'solanum lycopersicum,Solanum lycopersicum,eval/missing.jpg,0\n',
        encoding='utf-8')
    for sub in ('library', 'inat'):
        (root / 'distill' / sub).mkdir(parents=True)
        Image.new('RGB', (8, 8)).save(root / 'distill' / sub / f'{sub}_1.jpg')


def test_load_bundle_reads_everything_without_db(tmp_path):
    _fixture_bundle(tmp_path)
    b = load_bundle(tmp_path)
    assert b['class_keys'] == ['capsicum annuum', 'solanum lycopersicum']
    assert b['alpha'] == 0.0
    assert b['teacher_protos'].shape == (2, 4)
    # Eval paths resolve against the bundle; rows whose photo is missing are dropped.
    assert len(b['evals']) == 1
    assert b['evals'][0]['path'] == tmp_path / 'eval' / '11.jpg'
    assert b['evals'][0]['is_crop'] is True
    assert [p.parent.name for p in b['train_paths']] == ['inat', 'library']

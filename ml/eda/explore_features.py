"""
Exploratory Data Analysis for plant recommendation features.

Run from the project root:
    uv run python ml/eda/explore_features.py

Generates plots in ml/eda/plots/:
  - feature_distributions.png   histogram of each feature score
  - difficulty_breakdown.png    bar chart of easy/moderate/hard
  - zone_vs_season_scatter.png  scatter coloured by plant type
  - feature_correlation.png     heatmap of feature correlations
  - top10_bottom10.png          plants ranked by composite score
  - class_balance.png           success label distribution (if CSV exists)
  - feature_importance.png      feature importances (if trained model exists)
"""

import csv
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import matplotlib
matplotlib.use('Agg')   # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

from ml.features.build_features import build_feature_vector, score_plant

PLOT_DIR = Path(__file__).parent / 'plots'
DATA_CSV = _ROOT / 'ml' / 'data' / 'synthetic_training.csv'
MODEL_PKL = _ROOT / 'ml' / 'models' / 'recommender.pkl'

# Reference context used for all static visualisations
REF_CONTEXT = {
    'zone':                7,
    'sunlight_hours':      6,
    'current_month':       4,   # April
    'soil_ph':             6.5,
    'preferred_types':     ['vegetable', 'herb'],
    'current_plant_names': [],
}

GREEN = '#3a6b35'
PALETTE = sns.color_palette('Set2')


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_plants_from_db() -> list[dict]:
    try:
        api_path = str(_ROOT / 'apps' / 'api')
        if api_path not in sys.path:
            sys.path.insert(0, api_path)
        from app.main import create_app
        app = create_app()
        with app.app_context():
            from app.db.models import PlantLibrary
            plants = []
            for p in PlantLibrary.query.all():
                plants.append({
                    'id': p.id, 'name': p.name, 'type': p.type,
                    'min_zone': p.min_zone, 'max_zone': p.max_zone,
                    'sunlight': p.sunlight,
                    'soil_ph_min': p.soil_ph_min, 'soil_ph_max': p.soil_ph_max,
                    'good_neighbors': p.good_neighbors, 'difficulty': p.difficulty,
                    'days_to_harvest': p.days_to_harvest,
                    'fruit_months': p.fruit_months,
                    'bloom_months': p.bloom_months,
                    'growth_months': p.growth_months,
                })
            return plants
    except Exception as e:
        print(f'[warn] DB load failed ({e}); using fallback seed data.')
        return []


_FALLBACK_PLANTS = [
    {'id': 1,  'name': 'Tomato',      'type': 'vegetable', 'min_zone': 3, 'max_zone': 11, 'sunlight': 'Full sun',      'soil_ph_min': 6.0, 'soil_ph_max': 6.8, 'good_neighbors': '["Basil"]',   'difficulty': 'Moderate', 'days_to_harvest': 70, 'fruit_months': '[7,8,9]',    'bloom_months': '[6,7]',   'growth_months': '[5,6,7,8,9]'},
    {'id': 2,  'name': 'Basil',       'type': 'herb',      'min_zone': 4, 'max_zone': 11, 'sunlight': 'Full sun',      'soil_ph_min': 6.0, 'soil_ph_max': 7.0, 'good_neighbors': '["Tomato"]',  'difficulty': 'Easy',     'days_to_harvest': 30, 'fruit_months': None,         'bloom_months': '[7,8]',   'growth_months': '[5,6,7,8]'},
    {'id': 3,  'name': 'Lettuce',     'type': 'vegetable', 'min_zone': 4, 'max_zone': 9,  'sunlight': 'Partial shade', 'soil_ph_min': 6.0, 'soil_ph_max': 7.0, 'good_neighbors': '["Carrot"]',  'difficulty': 'Easy',     'days_to_harvest': 45, 'fruit_months': None,         'bloom_months': None,      'growth_months': '[3,4,5,9,10,11]'},
    {'id': 4,  'name': 'Carrot',      'type': 'vegetable', 'min_zone': 3, 'max_zone': 10, 'sunlight': 'Full sun',      'soil_ph_min': 6.0, 'soil_ph_max': 6.8, 'good_neighbors': '["Lettuce"]', 'difficulty': 'Moderate', 'days_to_harvest': 70, 'fruit_months': None,         'bloom_months': None,      'growth_months': '[3,4,5,6,7,8,9,10]'},
    {'id': 5,  'name': 'Zucchini',    'type': 'vegetable', 'min_zone': 4, 'max_zone': 10, 'sunlight': 'Full sun',      'soil_ph_min': 6.0, 'soil_ph_max': 7.5, 'good_neighbors': '["Basil"]',   'difficulty': 'Easy',     'days_to_harvest': 50, 'fruit_months': '[6,7,8,9]',  'bloom_months': '[6,7,8]', 'growth_months': '[5,6,7,8,9]'},
    {'id': 6,  'name': 'Kale',        'type': 'vegetable', 'min_zone': 2, 'max_zone': 9,  'sunlight': 'Full sun',      'soil_ph_min': 6.0, 'soil_ph_max': 7.5, 'good_neighbors': '["Beet"]',    'difficulty': 'Easy',     'days_to_harvest': 55, 'fruit_months': None,         'bloom_months': None,      'growth_months': '[3,4,5,9,10,11]'},
    {'id': 7,  'name': 'Cucumber',    'type': 'vegetable', 'min_zone': 4, 'max_zone': 11, 'sunlight': 'Full sun',      'soil_ph_min': 6.0, 'soil_ph_max': 7.0, 'good_neighbors': '["Dill"]',    'difficulty': 'Moderate', 'days_to_harvest': 55, 'fruit_months': '[7,8,9]',    'bloom_months': '[6,7,8]', 'growth_months': '[5,6,7,8,9]'},
    {'id': 8,  'name': 'Radish',      'type': 'vegetable', 'min_zone': 2, 'max_zone': 10, 'sunlight': 'Full sun',      'soil_ph_min': 6.0, 'soil_ph_max': 7.0, 'good_neighbors': '["Carrot"]',  'difficulty': 'Easy',     'days_to_harvest': 25, 'fruit_months': None,         'bloom_months': None,      'growth_months': '[3,4,5,9,10]'},
    {'id': 9,  'name': 'Mint',        'type': 'herb',      'min_zone': 3, 'max_zone': 11, 'sunlight': 'Partial shade', 'soil_ph_min': 6.0, 'soil_ph_max': 7.0, 'good_neighbors': '["Tomato"]',  'difficulty': 'Easy',     'days_to_harvest': 30, 'fruit_months': None,         'bloom_months': '[6,7,8]', 'growth_months': '[4,5,6,7,8,9]'},
    {'id': 10, 'name': 'Bell Pepper', 'type': 'vegetable', 'min_zone': 5, 'max_zone': 11, 'sunlight': 'Full sun',      'soil_ph_min': 6.0, 'soil_ph_max': 6.8, 'good_neighbors': '["Basil"]',   'difficulty': 'Moderate', 'days_to_harvest': 75, 'fruit_months': '[7,8,9]',    'bloom_months': '[6,7]',   'growth_months': '[5,6,7,8,9]'},
    {'id': 11, 'name': 'Sunflower',   'type': 'flower',    'min_zone': 2, 'max_zone': 11, 'sunlight': 'Full sun',      'soil_ph_min': 6.0, 'soil_ph_max': 7.5, 'good_neighbors': '["Cucumber"]', 'difficulty': 'Easy',    'days_to_harvest': 80, 'fruit_months': '[8,9,10]',   'bloom_months': '[7,8,9]', 'growth_months': '[4,5,6,7,8,9]'},
    {'id': 12, 'name': 'Spinach',     'type': 'vegetable', 'min_zone': 3, 'max_zone': 9,  'sunlight': 'Partial shade', 'soil_ph_min': 6.5, 'soil_ph_max': 7.5, 'good_neighbors': '["Pea"]',     'difficulty': 'Easy',     'days_to_harvest': 40, 'fruit_months': None,         'bloom_months': None,      'growth_months': '[3,4,5,9,10,11]'},
]


# ── Plot helpers ──────────────────────────────────────────────────────────────

def _save(fig, name: str):
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    path = PLOT_DIR / name
    fig.savefig(path, dpi=120, bbox_inches='tight')
    plt.close(fig)
    print(f'  Saved {path}')


# ── Plots ─────────────────────────────────────────────────────────────────────

def plot_feature_distributions(df: pd.DataFrame):
    feat_cols = ['zone_match', 'season_match', 'sunlight_match',
                 'soil_ph_match', 'difficulty', 'type_preference', 'composite_score']
    fig, axes = plt.subplots(2, 4, figsize=(14, 6))
    axes = axes.flatten()
    for i, col in enumerate(feat_cols):
        ax = axes[i]
        ax.hist(df[col], bins=15, color=GREEN, edgecolor='white', alpha=0.85)
        ax.set_title(col.replace('_', ' ').title(), fontsize=9)
        ax.set_xlabel('Score', fontsize=8)
        ax.set_ylabel('Count', fontsize=8)
        ax.tick_params(labelsize=7)
    axes[-1].set_visible(False)
    fig.suptitle(f'Feature Score Distributions (reference context: zone 7, April)', fontsize=11, fontweight='bold')
    plt.tight_layout()
    _save(fig, 'feature_distributions.png')


def plot_difficulty_breakdown(df: pd.DataFrame):
    counts = df['difficulty_label'].value_counts().reindex(['Easy', 'Moderate', 'Hard', 'Unknown'], fill_value=0)
    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(counts.index, counts.values, color=[GREEN, '#8dbf87', '#c9e0c6', '#e0e0e0'], edgecolor='white')
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                str(int(bar.get_height())), ha='center', va='bottom', fontsize=9)
    ax.set_title('Plant Difficulty Breakdown', fontsize=11, fontweight='bold')
    ax.set_ylabel('Number of Plants')
    _save(fig, 'difficulty_breakdown.png')


def plot_zone_vs_season(df: pd.DataFrame):
    types = df['type'].fillna('unknown').unique()
    color_map = {t: PALETTE[i % len(PALETTE)] for i, t in enumerate(types)}
    fig, ax = plt.subplots(figsize=(7, 5))
    for ptype, group in df.groupby('type'):
        ax.scatter(group['zone_match'], group['season_match'],
                   label=ptype, color=color_map.get(ptype, 'grey'),
                   alpha=0.8, s=60, edgecolors='white', linewidths=0.5)
        for _, row in group.iterrows():
            ax.annotate(row['name'], (row['zone_match'], row['season_match']),
                        fontsize=6, alpha=0.7, ha='center', va='bottom', xytext=(0, 3),
                        textcoords='offset points')
    ax.set_xlabel('Zone Match Score')
    ax.set_ylabel('Season Match Score')
    ax.set_title('Zone Match vs Season Match by Plant Type', fontsize=11, fontweight='bold')
    ax.legend(title='Type', fontsize=8, title_fontsize=8)
    ax.set_xlim(-0.1, 1.15)
    ax.set_ylim(-0.1, 1.15)
    _save(fig, 'zone_vs_season_scatter.png')


def plot_feature_correlation(df: pd.DataFrame):
    feat_cols = ['zone_match', 'season_match', 'sunlight_match',
                 'soil_ph_match', 'difficulty', 'type_preference',
                 'companion_bonus', 'composite_score']
    corr = df[feat_cols].corr()
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(corr, annot=True, fmt='.2f', cmap='RdYlGn',
                center=0, linewidths=0.5, ax=ax, annot_kws={'fontsize': 8})
    ax.set_title('Feature Correlation Matrix', fontsize=11, fontweight='bold')
    plt.tight_layout()
    _save(fig, 'feature_correlation.png')


def plot_top_bottom(df: pd.DataFrame, n: int = 10):
    sorted_df = df.sort_values('composite_score', ascending=False)
    top_n    = sorted_df.head(n)
    bottom_n = sorted_df.tail(n).iloc[::-1]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    for ax, subset, title, color in [
        (ax1, top_n,    f'Top {n} Plants',    GREEN),
        (ax2, bottom_n, f'Bottom {n} Plants', '#c97b5a'),
    ]:
        bars = ax.barh(subset['name'], subset['composite_score'], color=color, edgecolor='white')
        ax.set_xlim(0, 1.1)
        ax.set_xlabel('Composite Score')
        ax.set_title(title, fontsize=10, fontweight='bold')
        for bar in bars:
            ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height() / 2,
                    f'{bar.get_width():.2f}', va='center', fontsize=7)
    fig.suptitle(f'Plant Ranking — reference context: zone 7, April, 6h sun', fontsize=10)
    plt.tight_layout()
    _save(fig, 'top10_bottom10.png')


def plot_class_balance():
    if not DATA_CSV.exists():
        print(f'  [skip] {DATA_CSV} not found — run generate_synthetic.py first')
        return
    labels = []
    with open(DATA_CSV, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            labels.append(int(row['success']))
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.bar(['Success (1)', 'Failure (0)'], [n_pos, n_neg],
           color=[GREEN, '#c97b5a'], edgecolor='white')
    ax.set_title('Synthetic Training Set: Class Balance', fontsize=11, fontweight='bold')
    ax.set_ylabel('Count')
    for bar, val in zip(ax.patches, [n_pos, n_neg]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f'{val} ({100*val/len(labels):.1f}%)', ha='center', va='bottom', fontsize=9)
    _save(fig, 'class_balance.png')


def plot_feature_importance():
    if not MODEL_PKL.exists():
        print(f'  [skip] {MODEL_PKL} not found — run train_recommender.py first')
        return
    import pickle
    with open(MODEL_PKL, 'rb') as f:
        clf = pickle.load(f)
    feat_names = ['zone_match', 'season_match', 'sunlight_match',
                  'soil_ph_match', 'difficulty', 'type_preference', 'companion_bonus']
    importances = clf.feature_importances_
    pairs = sorted(zip(feat_names, importances), key=lambda x: x[1])
    names, vals = zip(*pairs)
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.barh(names, vals, color=GREEN, edgecolor='white')
    for bar in bars:
        ax.text(bar.get_width() + 0.002, bar.get_y() + bar.get_height() / 2,
                f'{bar.get_width():.3f}', va='center', fontsize=8)
    ax.set_xlabel('Feature Importance')
    ax.set_title('GBM Feature Importances', fontsize=11, fontweight='bold')
    plt.tight_layout()
    _save(fig, 'feature_importance.png')


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print('Loading plant data…')
    plants = _load_plants_from_db() or _FALLBACK_PLANTS
    print(f'  {len(plants)} plants loaded')

    print('Building feature vectors with reference context…')
    records = []
    for plant in plants:
        fv = build_feature_vector(plant, REF_CONTEXT)
        records.append({
            'id':               plant['id'],
            'name':             plant['name'],
            'type':             plant.get('type', 'unknown'),
            'difficulty_label': (plant.get('difficulty') or 'Unknown').capitalize(),
            'composite_score':  score_plant(plant, REF_CONTEXT),
            **fv,
        })
    df = pd.DataFrame(records)
    print(df[['name', 'composite_score']].sort_values('composite_score', ascending=False).to_string(index=False))

    print('\nGenerating plots…')
    plot_feature_distributions(df)
    plot_difficulty_breakdown(df)
    plot_zone_vs_season(df)
    plot_feature_correlation(df)
    plot_top_bottom(df)
    plot_class_balance()
    plot_feature_importance()

    print(f'\nAll plots saved to {PLOT_DIR}')


if __name__ == '__main__':
    main()

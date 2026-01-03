import sys
from pathlib import Path
import pandas as pd
import math

INPUT_FILENAME = 'sp4n-lapor_2021-2024.xlsx'
SHEET_NAME = 'Sheet1'
OUTPUT_CSV = 'data_gis_kecamatan_improved.csv'
OUTPUT_PNG = 'peta_sebaran_laporan_kecamatan_improved.png'
TOP_N = 40

# Minimal coordinates dictionary for known kecamatan. You can extend this.
coords = {
    'baleendah': (-6.9996, 107.6216),
    'margahayu': (-6.9717, 107.5847),
    'cileunyi': (-6.9400, 107.7300),
    'soreang': (-7.0252, 107.5259),
    'bojongsoang': (-6.9892, 107.6444),
    'banjaran': (-7.0450, 107.5900),
    'majalaya': (-7.0349, 107.7533),
    'margaasih': (-6.9480, 107.5400),
    'cangkuang': (-7.0700, 107.5500),
    'rancaekek': (-6.9600, 107.7700),
    'cicalengka': (-6.9875, 107.8401),
    'kutawaringin': (-6.9992, 107.5066),
    'ciparay': (-7.0350, 107.6500),
    'arjasari': (-7.0800, 107.6300),
    'katapang': (-7.0000, 107.5600),
    'ciwidey': (-7.0990, 107.4337),
    'cimenyan': (-6.8787, 107.6646),
    'cilengkrang': (-6.9050, 107.6941),
    'paseh': (-7.0313, 107.7905),
    'solokan jeruk': (-7.0100, 107.7300)
}


def normalize(s):
    if pd.isna(s):
        return ''
    return str(s).strip().casefold()


def resolve_paths():
    script_dir = Path(__file__).resolve().parent
    return {
        'input': script_dir / INPUT_FILENAME,
        'csv': script_dir / OUTPUT_CSV,
        'png': script_dir / OUTPUT_PNG,
    }


def aggregate(df):
    # Keep required columns
    cols = ['kecamatan_final', 'kota_kabupaten', 'provinsi']
    for c in cols:
        if c not in df.columns:
            raise KeyError(f"Kolom tidak ditemukan: {c}")

    df = df[cols].copy()
    # Filter to Bandung if possible
    mask = df['kota_kabupaten'].astype(str).str.contains('bandung', case=False, na=False)
    if mask.sum() > 0:
        df = df[mask]

    agg = df['kecamatan_final'].value_counts().reset_index()
    agg.columns = ['kecamatan', 'count']
    agg = agg.head(TOP_N).copy()
    agg['kecamatan_norm'] = agg['kecamatan'].apply(normalize)

    # map coordinates
    agg['lat'] = agg['kecamatan_norm'].map(lambda k: coords.get(k, (None, None))[0])
    agg['lon'] = agg['kecamatan_norm'].map(lambda k: coords.get(k, (None, None))[1])

    return agg


def make_interactive_map(df_agg, out_html):
    # Interactive map generation removed — only CSV and static PNG are produced.
    raise NotImplementedError('Interactive map removed in this variant. Use static map or integrate into app.py')


def make_static_map(df_agg, out_png):
    # Optional: generate a static map with GeoPandas + contextily
    try:
        import geopandas as gpd
        import matplotlib.pyplot as plt
        import contextily as ctx
        import seaborn as sns
    except Exception:
        print('GeoPandas/contextily not available — skipping static basemap. (Install geopandas, contextily, matplotlib)')
        return False

    valid = df_agg.dropna(subset=['lat', 'lon']).copy()
    if valid.empty:
        print('No valid coordinates for static map.')
        return False

    gdf = gpd.GeoDataFrame(
        valid,
        geometry=gpd.points_from_xy(valid['lon'], valid['lat']),
        crs='EPSG:4326'
    )

    # project to web mercator for contextily
    gdf = gdf.to_crs(epsg=3857)

    sns.set_style('white')
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))

    # scale sizes
    max_count = gdf['count'].max()
    gdf['size'] = gdf['count'].apply(lambda c: 50 + (c / max_count) * 1000)

    gdf.plot(ax=ax, markersize=gdf['size'], alpha=0.7, color='#e76f51', edgecolor='k', linewidth=0.4)

    # add labels
    for idx, row in gdf.iterrows():
        ax.text(row.geometry.x + 200, row.geometry.y + 200, row['kecamatan'], fontsize=9)

    # basemap
    try:
        ctx.add_basemap(ax, source=ctx.providers.Stamen.TonerLite)
    except Exception:
        try:
            ctx.add_basemap(ax)
        except Exception:
            print('Gagal menambahkan basemap dari contextily — melanjutkan tanpa basemap.')

    ax.set_axis_off()
    plt.tight_layout()
    fig.savefig(out_png, dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f'Static map saved to: {out_png}')
    return True


def main():
    paths = resolve_paths()
    input_path = paths['input']
    csv_path = paths['csv']
    png_path = paths['png']

    if not input_path.exists():
        print(f'Input file tidak ditemukan: {input_path}', file=sys.stderr)
        sys.exit(1)

    print(f'Reading: {input_path} (sheet: {SHEET_NAME})')
    try:
        df = pd.read_excel(input_path, sheet_name=SHEET_NAME, engine='openpyxl')
    except Exception as e:
        print('Gagal membaca file Excel:', e, file=sys.stderr)
        sys.exit(1)

    try:
        agg = aggregate(df)
    except KeyError as e:
        print('Masalah kolom:', e, file=sys.stderr)
        sys.exit(1)

    # Save CSV
    agg.to_csv(csv_path, index=False)
    print(f'Aggregated CSV saved to: {csv_path}')

    # Try static map (optional)
    try:
        made = make_static_map(agg, png_path)
        if not made:
            print('Static map not created (missing dependencies).')
    except Exception as e:
        print('Gagal membuat static map:', e, file=sys.stderr)


if __name__ == '__main__':
    main()

import pandas as pd
import json
import matplotlib.pyplot as plt
from pathlib import Path

def plot_bpp_psnr(title, results, out_path):
    plt.figure(figsize=(10, 6))
    
    for name, data in results.items():
        if not data:
            continue
        # Sort by bpp
        sorted_data = sorted(data, key=lambda x: x['bpp'])
        bpps = [x['bpp'] for x in sorted_data]
        psnrs = [x['psnr'] for x in sorted_data]
        
        plt.plot(bpps, psnrs, marker='o', linewidth=2, markersize=8, label=name)
        
    plt.title(title, fontsize=14)
    plt.xlabel('BPP (Bits Per Pixel)', fontsize=12)
    plt.ylabel('PSNR-RGB (dB)', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend(fontsize=11)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()

def main():
    root = Path(__file__).resolve().parents[4]
    
    # 1. Read data/baselines/kodak_vtm.json (Reference VTM)
    json_path = root / "data/baselines/kodak_vtm.json"
    with open(json_path) as f:
        ref_data = json.load(f)
    
    ref_bpps = ref_data["bpp"]
    ref_psnrs = ref_data["psnr"]
    qps = [22, 27, 32, 37]
    their_vtm_data = []
    for qp in qps:
        idx = qp - 15
        their_vtm_data.append({"qp": qp, "bpp": ref_bpps[idx], "psnr": ref_psnrs[idx]})
        
    results_dir = root / "docs" / "vtm_validation"

    # 2. Read VVenC 4:2:0 baseline
    vvenc_csv = results_dir / "vvenc_baseline.csv"
    vvenc_data = []
    if vvenc_csv.exists():
        df_vvenc = pd.read_csv(vvenc_csv)
        df_vvenc = df_vvenc[df_vvenc['mode'] == 'baseline']
        for qp in qps:
            df_qp = df_vvenc[df_vvenc['qp'] == qp]
            if not df_qp.empty:
                bpp = df_qp['bpp'].mean()
                psnr = df_qp['psnr_rgb'].mean()
                vvenc_data.append({"qp": qp, "bpp": bpp, "psnr": psnr})
                
    # 3. Read Canonical VTM FFmpeg 4:4:4
    ffmpeg_csv = results_dir / "vtm_ffmpeg.csv"
    ffmpeg_data = []
    if ffmpeg_csv.exists():
        df_ffmpeg = pd.read_csv(ffmpeg_csv)
        df_ffmpeg = df_ffmpeg[df_ffmpeg['mode'] == 'baseline']
        for qp in qps:
            df_qp = df_ffmpeg[df_ffmpeg['qp'] == qp]
            if not df_qp.empty:
                ffmpeg_data.append({"qp": qp, "bpp": df_qp['bpp'].mean(), "psnr": df_qp['psnr_rgb'].mean()})
                
    # 4. Read Replicated VTM OpenCV 4:4:4
    opencv_csv = results_dir / "vtm_opencv.csv"
    opencv_data = []
    if opencv_csv.exists():
        df_opencv = pd.read_csv(opencv_csv)
        if 'mode' in df_opencv.columns:
            df_opencv = df_opencv[df_opencv['mode'] == 'baseline']
        for qp in qps:
            df_qp = df_opencv[df_opencv['qp'] == qp]
            if not df_qp.empty:
                opencv_data.append({"qp": qp, "bpp": df_qp['bpp'].mean(), "psnr": df_qp['psnr_rgb'].mean()})
                
    # 5. Read Replicated VVenC OpenCV 4:2:0
    vvenc_opencv_csv = results_dir / "vvenc_opencv.csv"
    vvenc_opencv_data = []
    if vvenc_opencv_csv.exists():
        df_vvenc_opencv = pd.read_csv(vvenc_opencv_csv)
        for qp in qps:
            df_qp = df_vvenc_opencv[df_vvenc_opencv['qp'] == qp]
            if not df_qp.empty:
                vvenc_opencv_data.append({"qp": qp, "bpp": df_qp['bpp'].mean(), "psnr": df_qp['psnr_rgb'].mean()})
                
    # Generate Scenario 1 plot: Replication
    plot_bpp_psnr(
        "VTM 18.0 Replication (OpenCV 4:4:4) vs VVenC (4:2:0)",
        {
            "VTM 18.0 (Duan et al. Repo)": their_vtm_data,
            "Replicated VTM (OpenCV 4:4:4)": opencv_data,
            "Replicated VVenC (OpenCV 4:2:0)": vvenc_opencv_data
        },
        root / "docs" / "vtm_validation" / "plot_replication.png"
    )
    
    # Generate Scenario 2 plot: Canonical
    plot_bpp_psnr(
        "Canonical (FFmpeg) vs Full-Range Penalty (OpenCV)",
        {
            "VTM Canonical (FFmpeg 4:4:4)": ffmpeg_data,
            "VTM OpenCV 4:4:4 (Duan et al.)": opencv_data,
            "VVenC Canonical (FFmpeg 4:2:0)": vvenc_data,
            "VVenC OpenCV 4:2:0": vvenc_opencv_data
        },
        root / "docs" / "vtm_validation" / "plot_canonical.png"
    )
    
    print("Plots generated successfully in docs/vtm_validation/")

if __name__ == "__main__":
    main()

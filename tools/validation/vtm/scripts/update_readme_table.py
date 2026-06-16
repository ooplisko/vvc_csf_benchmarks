import pandas as pd
import json
import re
from pathlib import Path

def main():
    root = Path(__file__).resolve().parents[4]
    vtm_dir = root / "tools" / "vtm_validation"
    results_dir = vtm_dir / "results"
    
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
        df_opencv = df_opencv[df_opencv['mode'] == 'baseline']
        for qp in qps:
            df_qp = df_opencv[df_opencv['qp'] == qp]
            if not df_qp.empty:
                opencv_data.append({"qp": qp, "bpp": df_qp['bpp'].mean(), "psnr": df_qp['psnr_rgb'].mean()})

    ref_link = "https://github.com/duanzhiihao/lossy-vae/blob/main/results/kodak/kodak-vtm18.0.json"
    opencv_link = "results/vtm_opencv.csv"
    ffmpeg_link = "results/vtm_ffmpeg.csv"
    vvenc_link = "results/vvenc_baseline.csv"

    # Generate Markdown Table
    table = "| QP | [Duan et al. VTM BPP](" + ref_link + ") | [Replicated VTM OpenCV BPP](" + opencv_link + ") | [Canonical VTM FFmpeg BPP](" + ffmpeg_link + ") | [VVenC Baseline BPP](" + vvenc_link + ") | [Duan et al. VTM PSNR-RGB](" + ref_link + ") | [Replicated VTM OpenCV PSNR-RGB](" + opencv_link + ") | [Canonical VTM FFmpeg PSNR-RGB](" + ffmpeg_link + ") | [VVenC Baseline PSNR-RGB](" + vvenc_link + ") |\n"
    table += "|----|------------------------|--------------------|--------------------|---------------|----------------------------|---------------------------|---------------------------|--------------------|\n"
    
    for i, qp in enumerate(qps):
        ref_bpp = f"{their_vtm_data[i]['bpp']:.5f}"
        ref_psnr = f"{their_vtm_data[i]['psnr']:.5f}"
        
        cv_bpp = f"**{opencv_data[i]['bpp']:.5f}**" if opencv_data else "N/A"
        cv_psnr = f"{opencv_data[i]['psnr']:.5f}" if opencv_data else "N/A"
        
        ff_bpp = f"{ffmpeg_data[i]['bpp']:.5f}" if ffmpeg_data else "N/A"
        ff_psnr = f"{ffmpeg_data[i]['psnr']:.5f}" if ffmpeg_data else "N/A"
        
        vv_bpp = f"{vvenc_data[i]['bpp']:.5f}" if vvenc_data else "N/A"
        vv_psnr = f"{vvenc_data[i]['psnr']:.5f}" if vvenc_data else "N/A"
        
        table += f"| {qp} | {ref_bpp:<15} | {cv_bpp:<18} | {ff_bpp:<18} | {vv_bpp:<13} | {ref_psnr:<12} | {cv_psnr:<25} | {ff_psnr:<25} | {vv_psnr:<18} |\n"

    readme_path = vtm_dir / "README.md"
    content = readme_path.read_text(encoding="utf-8")
    
    # Replace table
    table_pattern = re.compile(r"\| QP \| \[Duan et al.*?\|.*?(\n\n|\Z)", re.DOTALL)
    if not table_pattern.search(content):
        # Fallback if old header still there
        table_pattern = re.compile(r"\| QP \| \[Ref BPP.*?\|.*?(\n\n|\Z)", re.DOTALL)
        
    if table_pattern.search(content):
        content = table_pattern.sub(table + "\n", content)
    else:
        print("Could not find table to replace!")
        
    readme_path.write_text(content, encoding="utf-8")
    print("README updated.")

if __name__ == "__main__":
    main()

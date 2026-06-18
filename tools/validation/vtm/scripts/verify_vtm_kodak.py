import sys
import json
import csv
from pathlib import Path
import subprocess

def run_benchmark():
    root = Path(__file__).resolve().parents[4]
    
    # 4 standard points: QPs 22, 27, 32, 37
    qps = "22,27,32,37"
    
    vtm_encoder = root / "binaries" / "vtm" / "EncoderApp.exe"
    vtm_decoder = root / "binaries" / "vtm" / "DecoderApp.exe"
    
    # Output results to results/image_kodak_vtm
    run_dir = root / "results" / "image_kodak_vtm"
    
    cmd = [
        sys.executable,
        str(root / "tools" / "benchmarking" / "image_csf_benchmark.py"),
        "--root", str(run_dir),
        "--png-dir", str(root / "data" / "datasets" / "images" / "kodak" / "png"),
        "--qps", qps,
        "--baseline-encoder", str(vtm_encoder),
        "--csf-encoder", str(vtm_encoder),
        "--decoder", str(vtm_decoder),
        "--conversion", "opencv_444"
    ]
    
    print("Running VTM Benchmark...", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return run_dir / "image_metrics.csv"

def compare_results(csv_file):
    root = Path(__file__).resolve().parents[4]
    json_file = root / "data" / "baselines" / "kodak_vtm.json"
    
    with open(json_file, 'r') as f:
        ref_data = json.load(f)
    
    ref_bpp = ref_data["bpp"]
    ref_psnr = ref_data["psnr"]
    
    # Read CSV and calculate averages
    from collections import defaultdict
    aggregated = defaultdict(lambda: {"bpp": 0.0, "psnr_rgb": 0.0, "psnr_y": 0.0, "count": 0})
    
    with open(csv_file, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            qp = int(row["qp"])
            aggregated[qp]["bpp"] += float(row["bpp"])
            aggregated[qp]["psnr_rgb"] += float(row["psnr_rgb"])
            aggregated[qp]["psnr_y"] += float(row["psnr_y"])
            aggregated[qp]["count"] += 1
            
    results = {}
    for qp, data in aggregated.items():
        if data["count"] > 0:
            results[qp] = {
                "bpp": data["bpp"] / data["count"],
                "psnr_rgb": data["psnr_rgb"] / data["count"],
                "psnr_y": data["psnr_y"] / data["count"]
            }
    
    # Compare only the standard 4 QPs
    target_qps = [22, 27, 32, 37]
    
    print("\n--- VTM 18.0 Kodak Validation ---")
    print(f"{'QP':<5} | {'Ref BPP':<10} | {'Rep BPP':<10} | {'Ref PSNR':<10} | {'Rep PSNR-RGB':<12} | {'Rep PSNR-Y':<12}")
    print("-" * 75)
    
    for qp in target_qps:
        if qp not in results:
            print(f"{qp:<5} | MISSING IN RESULTS")
            continue
            
        # The reference JSON starts at QP 15, so index is qp - 15
        idx = qp - 15
        r_bpp = ref_bpp[idx]
        r_psnr = ref_psnr[idx]
        
        o_bpp = results[qp]["bpp"]
        o_psnr_rgb = results[qp]["psnr_rgb"]
        o_psnr_y = results[qp]["psnr_y"]
        
        print(f"{qp:<5} | {r_bpp:<10.5f} | {o_bpp:<10.5f} | {r_psnr:<10.5f} | {o_psnr_rgb:<12.5f} | {o_psnr_y:<12.5f}")

if __name__ == "__main__":
    csv_out = run_benchmark()
    compare_results(csv_out)

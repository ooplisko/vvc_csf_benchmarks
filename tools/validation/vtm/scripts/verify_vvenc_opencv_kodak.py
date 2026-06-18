import os
import subprocess
import glob
from pathlib import Path
import cv2
import numpy as np
import csv

def get_bpp(vvc_path, h, w):
    return os.path.getsize(vvc_path) * 8 / (h * w)

def run_opencv_vvenc(impath, qp):
    original = cv2.imread(impath)
    h, w = original.shape[:2]
    
    original_rgb = cv2.cvtColor(original, cv2.COLOR_BGR2RGB)
    yuv_i420 = cv2.cvtColor(original, cv2.COLOR_BGR2YUV_I420)
    
    temp_yuv = 'temp_cv_kodak.yuv'
    with open(temp_yuv, 'wb') as f:
        f.write(yuv_i420.tobytes())
        
    root = Path(__file__).resolve().parents[4]
    vvenc = str(root / "binaries" / "vvenc_default.exe")
    vvdec = str(root / "binaries" / "vvdecapp.exe")
        
    # VVenC
    cmd = f'"{vvenc}" -i {temp_yuv} -s {w}x{h} -q {qp} --fps 1 -b temp_cv_kodak.vvc --threads 4 > NUL 2>&1'
    subprocess.run(cmd, shell=True)
    bpp = get_bpp('temp_cv_kodak.vvc', h, w)
    
    # VVdeC
    cmd_dec = f'"{vvdec}" -b temp_cv_kodak.vvc -o temp_dec_kodak.yuv > NUL 2>&1'
    subprocess.run(cmd_dec, shell=True)
    
    with open('temp_dec_kodak.yuv', 'rb') as f:
        yuv_data = f.read()
        
    # Read 10-bit output
    decoded_yuv16 = np.frombuffer(yuv_data, dtype=np.uint16).reshape((h * 3 // 2, w))
    decoded_yuv = np.clip((decoded_yuv16 + 2) >> 2, 0, 255).astype(np.uint8)
    
    # Decode to BGR using OpenCV limited to full range mapping
    decoded_bgr = cv2.cvtColor(decoded_yuv, cv2.COLOR_YUV2BGR_I420)
    
    psnr = cv2.PSNR(original, decoded_bgr)
    
    # Cleanup
    for f in [temp_yuv, 'temp_cv_kodak.vvc', 'temp_dec_kodak.yuv']:
        if os.path.exists(f):
            os.remove(f)
            
    return bpp, psnr

def main():
    root = Path(__file__).resolve().parents[4]
    kodak_dir = root / "data" / "datasets" / "images" / "kodak" / "png"
    out_csv = root / "docs" / "vtm_validation" / "vvenc_opencv.csv"
    
    qps = [22, 27, 32, 37]
    images = sorted(glob.glob(str(kodak_dir / "kodim*.png")))
    
    if not images:
        print(f"No images found in {kodak_dir}")
        return
        
    results = []
    
    print(f"Running VVenC OpenCV Pipeline on {len(images)} images for QPs {qps}...")
    for qp in qps:
        qp_bpp = 0
        qp_psnr = 0
        
        for impath in images:
            bpp, psnr = run_opencv_vvenc(impath, qp)
            qp_bpp += bpp
            qp_psnr += psnr
            print(f"  {os.path.basename(impath)} (QP {qp}): BPP {bpp:.4f}, PSNR {psnr:.4f}")
            
        avg_bpp = qp_bpp / len(images)
        avg_psnr = qp_psnr / len(images)
        
        print(f"Average for QP {qp}: BPP {avg_bpp:.4f}, PSNR {avg_psnr:.4f}\n")
        results.append({
            'qp': qp,
            'bpp': avg_bpp,
            'psnr_rgb': avg_psnr
        })
        
    with open(out_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['qp', 'bpp', 'psnr_rgb'])
        writer.writeheader()
        writer.writerows(results)
        
    print(f"Results written to {out_csv}")

if __name__ == '__main__':
    main()

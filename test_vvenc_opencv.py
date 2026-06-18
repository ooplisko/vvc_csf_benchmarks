import cv2
import numpy as np
import subprocess
import os

def get_bpp(vvc_path, h, w):
    return os.path.getsize(vvc_path) * 8 / (h * w)

def run_opencv_pipeline(impath, qp):
    original = cv2.imread(impath)
    h, w = original.shape[:2]
    
    # Encode to YUV I420
    yuv_i420 = cv2.cvtColor(original, cv2.COLOR_BGR2YUV_I420)
    temp_yuv = 'temp_cv.yuv'
    with open(temp_yuv, 'wb') as f:
        f.write(yuv_i420.tobytes())
        
    # VVenC
    cmd = f".\\binaries\\vvenc_default.exe -i {temp_yuv} -s {w}x{h} -q {qp} --fps 1 -b temp_cv.vvc --threads 4"
    subprocess.run(cmd, shell=True)
    bpp = get_bpp('temp_cv.vvc', h, w)
    
    # VVdeC
    cmd_dec = f".\\binaries\\vvdecapp.exe -b temp_cv.vvc -o temp_dec.yuv > NUL 2>&1"
    subprocess.run(cmd_dec, shell=True)
    
    with open('temp_dec.yuv', 'rb') as f:
        yuv_data = f.read()
        
    decoded_yuv16 = np.frombuffer(yuv_data, dtype=np.uint16).reshape((h * 3 // 2, w))
    decoded_yuv = np.clip((decoded_yuv16 + 2) >> 2, 0, 255).astype(np.uint8)
    decoded_bgr = cv2.cvtColor(decoded_yuv, cv2.COLOR_YUV2BGR_I420)
    
    psnr = cv2.PSNR(original, decoded_bgr) # PSNR-RGB is same as PSNR-BGR
    
    # Cleanup
    os.remove('temp_cv.yuv')
    os.remove('temp_cv.vvc')
    os.remove('temp_dec.yuv')
    
    return bpp, psnr

def run_ffmpeg_pipeline(impath, qp):
    original = cv2.imread(impath)
    h, w = original.shape[:2]
    temp_yuv = 'temp_ff.yuv'
    
    # Convert BGR -> YUV420p via FFmpeg
    cmd_ff_enc = f"ffmpeg -y -i {impath} -pix_fmt yuv420p -hide_banner -loglevel error {temp_yuv}"
    subprocess.run(cmd_ff_enc, shell=True)
    
    cmd = f".\\binaries\\vvenc_default.exe -i {temp_yuv} -s {w}x{h} -q {qp} --fps 1 -b temp_ff.vvc --threads 4 > NUL 2>&1"
    subprocess.run(cmd, shell=True)
    bpp = get_bpp('temp_ff.vvc', h, w)
    
    # VVdeC
    cmd_dec = f".\\binaries\\vvdecapp.exe -b temp_ff.vvc -o temp_dec_ff.yuv > NUL 2>&1"
    subprocess.run(cmd_dec, shell=True)
    
    # Convert YUV420p10le -> PNG via FFmpeg for PSNR
    decoded_png = 'temp_dec_ff.png'
    cmd_ff_dec = f"ffmpeg -y -s {w}x{h} -pix_fmt yuv420p10le -i temp_dec_ff.yuv -hide_banner -loglevel error {decoded_png}"
    subprocess.run(cmd_ff_dec, shell=True)
    
    decoded = cv2.imread(decoded_png)
    psnr = cv2.PSNR(original, decoded)
    
    # Cleanup
    os.remove('temp_ff.yuv')
    os.remove('temp_ff.vvc')
    os.remove('temp_dec_ff.yuv')
    os.remove('temp_dec_ff.png')
    
    return bpp, psnr

if __name__ == '__main__':
    impath = 'data/datasets/images/kodak/png/kodim01.png'
    qp = 22
    
    print("Testing OpenCV 4:2:0 Pipeline...")
    bpp_cv, psnr_cv = run_opencv_pipeline(impath, qp)
    print(f"OpenCV: BPP = {bpp_cv:.5f}, PSNR = {psnr_cv:.5f}")
    
    print("\nTesting FFmpeg 4:2:0 Pipeline...")
    bpp_ff, psnr_ff = run_ffmpeg_pipeline(impath, qp)
    print(f"FFmpeg: BPP = {bpp_ff:.5f}, PSNR = {psnr_ff:.5f}")
    
    print("\nDifference (FFmpeg - OpenCV):")
    print(f"Delta BPP: {bpp_ff - bpp_cv:.5f}")
    print(f"Delta PSNR: {psnr_ff - psnr_cv:.5f}")

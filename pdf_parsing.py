"""
torch==2.2.2+cu121
torchvision==0.17.2+cu121
torchaudio==2.2.2+cu121
--extra-index-url https://download.pytorch.org/whl/cu121
nougat-ocr
albumentations==1.3.0
transformers==4.36.2
pynougat[all]
"""


nougat ./pdfs/229.pdf -o ./pdfs/ --recompute

nougat --markdown --no-skipping --batchsize 1 --full-precision ./pdfs/229.pdf --out ./pdfs/

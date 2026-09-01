#!/usr/bin/env python
"""Test single PDF conversion"""

import fitz
import time
import io
import sys
sys.path.insert(0, r"D:\Claude\projects\2hao-analyst")

from mineru.backend.pipeline.model_init import HybridModelSingleton
from mineru.backend.pipeline.batch_analyze import BatchAnalyze
from mineru.backend.pipeline.pipeline_middle_json_mkcontent import union_make, MakeMode
from mineru.backend.pipeline.model_init import HybridModelSingleton

# Monkey patch
from mineru.backend.pipeline.model_init import HybridModelSingleton
original_get_model = HybridModelSingleton.get_model
def patched_get_model(self, lang=None, formula_enable=None, table_enable=None):
    return original_get_model(self, lang=lang, formula_enable=formula_enable)
HybridModelSingleton.get_model = patched_get_model

# Initialize model manager ONCE
model_manager = HybridModelSingleton(
    formula_config={"enable": True},
    table_config={"enable": True},
    lang="ch",
    device="cpu",
)

batch_analyzer = BatchAnalyze(
    model_manager=HybridModelSingleton(
        formula_config={"enable": True},
        table_config={"enable": True},
        lang="ch",
        device="cpu",
    ),
    batch_ratio=1,
    formula_enable=True,
    table_enable=True,
)

import fitz
import time
import io
from PIL import Image

pdf_path = r"D:\Claude\test_simple.pdf"
doc = fitz.open(pdf_path)
print(f"PDF pages: {len(doc)}")

# Test with first page only
page = doc[0]
pix = page.get_pixmap(dpi=200)
img = pix.tobytes("png")

from PIL import Image
import io
pil_img = Image.open(io.BytesIO(img))
images_with_extra_info = [(pil_img, True, "ch")]

start = time.time()
result = batch_analyzer(images_with_extra_info)
print(f"Page processed in {time.time() - start:.1f}s")

# Check result structure
print(f"Result type: {type(result)}")
print(f"Result length: {len(result)}")
if result and isinstance(result[0], list):
    print(f"  Inner list length: {len(result[0])}")
    for i, item in enumerate(result[0][:3]):
        if isinstance(item, dict):
            print(f"  Item {i}: {list(item.keys())}")
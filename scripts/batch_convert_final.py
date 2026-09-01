#!/usr/bin/env python
"""
Efficient batch PDF to Markdown conversion using MinerU Python API directly.
Processes all PDFs in benchmark/golden_raw/ and outputs markdown to benchmark/golden/
"""

import fitz
import time
import io
import os
import json
import sys
import traceback
from pathlib import Path

# MinerU imports
from mineru.backend.pipeline.model_init import HybridModelSingleton
from mineru.backend.pipeline.batch_analyze import BatchAnalyze
from mineru.backend.pipeline.pipeline_middle_json_mkcontent import union_make, MakeMode
from mineru.backend.pipeline.model_init import HybridModelSingleton
from mineru.utils.enum_class import BlockType

# Monkey patch HybridModelSingleton.get_model to accept table_enable parameter
from mineru.backend.pipeline.model_init import HybridModelSingleton
original_get_model = HybridModelSingleton.get_model
def patched_get_model(self, lang=None, formula_enable=None, table_enable=None):
    return original_get_model(self, lang=lang, formula_enable=formula_enable)
HybridModelSingleton.get_model = patched_get_model

# Label mapping from batch_analyze output to BlockType values
LABEL_TO_BLOCKTYPE = {
    'text': 'text',
    'title': 'title',
    'list': 'list',
    'index': 'index',
    'abstract': 'abstract',
    'ref_text': 'ref_text',
    'interline_equation': 'interline_equation',
    'image': 'image',
    'chart': 'chart',
    'table': 'table',
    'code': 'code',
    'aside_text': 'aside_text',
    'caption': 'caption',
    'footer': 'footer',
    'footer_image': 'footer_image',
    'footnote': 'footnote',
    'formula_number': 'formula_number',
    'header': 'header',
    'header_image': 'header_image',
    'image_body': 'image_body',
    'image_caption': 'image_caption',
    'image_footnote': 'image_footnote',
    'interline_equation': 'interline_equation',
    'index': 'index',
    'ref_text': 'ref_text',
    'table': 'table',
    'text': 'text',
    'title': 'title',
    'vertical_text': 'vertical_text',
    'discarded': 'discarded',
    'algorithm': 'algorithm',
    'algorithm_caption': 'algorithm_caption',
    'aside_text': 'aside_text',
    'chart': 'chart',
    'chart_body': 'chart_body',
    'chart_caption': 'chart_caption',
    'chart_footnote': 'chart_footnote',
    'code': 'code',
    'code_body': 'code_body',
    'code_caption': 'code_caption',
    'code_footnote': 'code_footnote',
    'discarded': 'discarded',
    'algorithm': 'algorithm',
    'algorithm_caption': 'algorithm_caption',
    'aside_text': 'aside_text',
    'chart': 'chart',
    'chart_body': 'chart_body',
    'chart_caption': 'chart_caption',
    'chart_footnote': 'chart_footnote',
    'code': 'code',
    'code_body': 'code_body',
    'code_caption': 'code_caption',
    'code_footnote': 'code_footnote',
    'discarded': 'discarded',
}

def label_to_blocktype(label: str) -> str:
    label_lower = label.lower().replace(' ', '_').replace('-', '_')
    return LABEL_TO_BLOCKTYPE.get(label.lower(), 'text')


def process_pdf(pdf_path: str, batch_analyzer) -> str:
    import fitz
    import time
    import io
    from PIL import Image
    from mineru.backend.pipeline.pipeline_middle_json_mkcontent import union_make, MakeMode

    doc = fitz.open(pdf_path)
    markdown_parts = []
    
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=200)
            img = pix.tobytes('png')
            
            from PIL import Image
            import io
            pil_img = Image.open(io.BytesIO(img))
            
            images_with_extra_info = [(pil_img, True, 'ch')]
            
            result = batch_analyzer([(pil_img, True, 'ch')])
            
            para_blocks = []
            
            if result and isinstance(result[0], list):
                for item in result[0]:
                    if not isinstance(item, dict):
                        continue
                    
                    label = item.get('label', '')
                    text_content = item.get('text', item.get('content', ''))
                    bbox = item.get('bbox', [0, 0, 0, 0])
                    score = item.get('score', 0.0)
                    index = item.get('index', 0)
                    label = item.get('label', '')
                    
                    label_lower = label.lower().replace(' ', '_').replace('-', '_')
                    block_type = LABEL_TO_BLOCKTYPE.get(label.lower(), 'text')
                    
                    para_block = {
                        'type': block_type,
                        'bbox': bbox,
                        'score': score,
                        'index': index,
                    }
                    
                    if text_content:
                        para_block = {
                            'type': block_type,
                            'bbox': bbox,
                            'score': score,
                            'index': index,
                            'lines': [{
                                'spans': [{
                                    'content': text_content,
                                    'bbox': bbox,
                                }]
                            }]
                        }
                    else:
                        para_block = {
                            'type': block_type,
                            'bbox': bbox,
                            'score': score,
                            'index': index,
                            'lines': [{
                                'spans': [{
                                    'content': '',
                                    'bbox': [0, 0, 0, 0],
                                }]
                            }]
                        }
                    
                    para_blocks.append(para_block)
            
            page_info = {
                'page_idx': 0,
                'page_size': [200, 200],
                'para_blocks': para_blocks,
                'discarded_blocks': [],
                'page_idx': 0,
                'page_size': [200, 200],
            }
            
            md = union_make([page_info], 'mm_markdown', 'images')
            markdown_parts.append(md)
            
        return '\n\n'.join(markdown_parts)
            
    except Exception as e:
        print(f'Error processing page: {e}')
        return ''
    finally:
        doc.close()


def label_to_blocktype(label: str) -> str:
    label_lower = label.lower().replace(' ', '_').replace('-', '_')
    return LABEL_TO_BLOCKTYPE.get(label.lower(), 'text')


def process_pdf_file(pdf_path: str, output_dir: str, batch_analyzer, doc_stem: str) -> bool:
    try:
        md = process_pdf(pdf_path, batch_analyzer)
        if md:
            output_path = Path(output_dir) / f"{Path(pdf_path).stem}.md"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(md, encoding='utf-8')
            return True
        return False
    except Exception as e:
        print(f'Error processing {pdf_path}: {e}')
        traceback.print_exc()
        return False


def main():
    # Monkey patch HybridModelSingleton.get_model
    from mineru.backend.pipeline.model_init import HybridModelSingleton
    original_get_model = HybridModelSingleton.get_model
    def patched_get_model(self, lang=None, formula_enable=None, table_enable=None):
        return original_get_model(self, lang=lang, formula_enable=formula_enable)
    HybridModelSingleton.get_model = patched_get_model

    model_manager = HybridModelSingleton(
        formula_config={'enable': True},
        table_config={'enable': True},
        lang='ch',
        device='cpu',
    )

    batch_analyzer = BatchAnalyze(
        model_manager=HybridModelSingleton(
            formula_config={'enable': True},
            table_config={'enable': True},
            lang='ch',
            device='cpu',
        ),
        batch_ratio=1,
        formula_enable=True,
        table_enable=True,
    )

    input_root = Path('benchmark/golden_raw')
    output_root = Path('benchmark/golden')
    output_root.mkdir(parents=True, exist_ok=True)

    categories = ['listed_company', 'industry_deep', 'unlisted_company', 'earnings_notes', 'decision_memo']

    for category in categories:
        input_dir = Path('benchmark/golden_raw') / category
        output_dir = Path('benchmark/golden') / category
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if not input_dir.exists():
            print(f'Skipping {category}: input directory not found')
            continue
        
        pdf_files = list(input_dir.glob('*.pdf'))
        if not pdf_files:
            print(f'No PDF files in {category}')
            continue
        
        print(f'\nProcessing {category}: {len(pdf_files)} PDFs')
        
        success_count = 0
        for pdf_file in pdf_files:
            try:
                if process_pdf_file(str(pdf_file), str(output_dir), batch_analyzer, pdf_file.stem):
                    print(f'  [OK] {pdf_file.name}')
                    success_count += 1
                else:
                    print(f'  [FAIL] {pdf_file.name}: Failed')
            except Exception as e:
                print(f'  [FAIL] {pdf_file.name}: {e}')
        
        print(f'Completed {category}: {success_count}/{len(pdf_files)} successful')

    print('\n=== Batch conversion complete ===')


if __name__ == '__main__':
    main()

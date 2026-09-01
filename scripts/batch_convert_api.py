#!/usr/bin/env python
"""
Efficient batch PDF to Markdown conversion using MinerU Python API directly.
This script processes all PDFs in benchmark/golden_raw/ and outputs markdown to benchmark/golden/
"""

import fitz
import time
import io
import os
import json
import sys
from pathlib import Path
from PIL import Image

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

# Label mapping from batch_analyze output to BlockType
LABEL_TO_BLOCKTYPE = {
    'text': BlockType.TEXT,
    'title': BlockType.TITLE,
    'list': BlockType.LIST,
    'index': BlockType.INDEX,
    'abstract': BlockType.ABSTRACT,
    'ref_text': BlockType.REF_TEXT,
    'title': BlockType.TITLE,
    'interline_equation': BlockType.INTERLINE_EQUATION,
    'image': BlockType.IMAGE,
    'chart': BlockType.CHART,
    'table': BlockType.TABLE,
    'code': BlockType.CODE,
    'aside_text': BlockType.ASIDE_TEXT,
    'caption': BlockType.CAPTION,
    'footer': BlockType.FOOTER,
    'footer_image': BlockType.FOOTER_IMAGE,
    'footnote': BlockType.FOOTNOTE,
    'formula_number': BlockType.FORMULA_NUMBER,
    'header': BlockType.HEADER,
    'header_image': BlockType.HEADER_IMAGE,
    'image_body': BlockType.IMAGE_BODY,
    'image_caption': BlockType.IMAGE_CAPTION,
    'image_footnote': BlockType.IMAGE_FOOTNOTE,
    'interline_equation': BlockType.INTERLINE_EQUATION,
    'index': BlockType.INDEX,
    'ref_text': BlockType.REF_TEXT,
    'table': BlockType.TABLE,
    'text': BlockType.TEXT,
    'title': BlockType.TITLE,
    'vertical_text': BlockType.VERTICAL_TEXT,
    'discarded': BlockType.DISCARDED,
    'algorithm': BlockType.ALGORITHM,
    'algorithm_caption': BlockType.ALGORITHM_CAPTION,
    'aside_text': BlockType.ASIDE_TEXT,
    'chart': BlockType.CHART,
    'chart_body': BlockType.CHART_BODY,
    'chart_caption': BlockType.CHART_CAPTION,
    'chart_footnote': BlockType.CHART_FOOTNOTE,
    'code': BlockType.CODE,
    'code_body': BlockType.CODE_BODY,
    'code_caption': BlockType.CODE_CAPTION,
    'code_footnote': BlockType.CODE_FOOTNOTE,
    'discarded': BlockType.DISCARDED,
    'doc_title': BlockType.DOC_TITLE,
    'equation': BlockType.EQUATION,
    'footer': BlockType.FOOTER,
    'footer_image': BlockType.FOOTER_IMAGE,
    'footnote': BlockType.FOOTNOTE,
    'formula_number': BlockType.FORMULA_NUMBER,
    'header': BlockType.HEADER,
    'header_image': BlockType.HEADER_IMAGE,
    'image_body': BlockType.IMAGE_BODY,
    'image_caption': BlockType.IMAGE_CAPTION,
    'image_footnote': BlockType.IMAGE_FOOTNOTE,
    'interline_equation': BlockType.INTERLINE_EQUATION,
    'index': BlockType.INDEX,
    'interline_equation': BlockType.INTERLINE_EQUATION,
    'list': BlockType.LIST,
    'page_footnote': BlockType.PAGE_FOOTNOTE,
    'page_number': BlockType.PAGE_NUMBER,
    'paragraph_title': BlockType.PARAGRAPH_TITLE,
    'phonetic': BlockType.PHONETIC,
    'ref_text': BlockType.REF_TEXT,
    'table': BlockType.TABLE,
    'table_body': BlockType.TABLE_BODY,
    'table_caption': BlockType.TABLE_CAPTION,
    'table_footnote': BlockType.TABLE_FOOTNOTE,
    'text': BlockType.TEXT,
    'title': BlockType.TITLE,
    'vertical_text': BlockType.VERTICAL_TEXT,
}

def label_to_blocktype(label: str) -> str:
    """Convert label from batch_analyze to BlockType value."""
    label_lower = label.lower().replace(' ', '_').replace('-', '_')
    return LABEL_TO_BLOCKTYPE.get(label_lower, BlockType.TEXT)


def convert_batch_result_to_page_info(page_idx: int, page_size: list, batch_result: list) -> dict:
    """Convert batch_analyze output to page_info dict for union_make."""
    para_blocks = []
    discarded_blocks = []
    
    for item in batch_result:
        if not isinstance(item, dict):
            continue
            
        label = item.get('label', '').lower()
        block_type = label_to_blocktype(item.get('label', ''))
        
        para_block = {
            'type': label_to_blocktype(item.get('label', '')),
            'bbox': item.get('bbox', [0, 0, 0, 0]),
            'score': item.get('score', 0.0),
            'index': item.get('index', 0),
        }
        
        # Add lines/spans structure for text blocks
        if 'text' in item:
            para_block['lines'] = [{
                'spans': [{
                    'content': item.get('text', ''),
                    'bbox': item.get('bbox', [0, 0, 0, 0]),
                }]
            }]
        
        # Add lines/spans for text blocks
        if 'label' in item and item.get('label', '').lower() in ['text', 'title', 'list', 'index', 'abstract', 'ref_text']:
            if 'text' not in item and 'content' in item:
                para_block['lines'] = [{
                    'spans': [{
                        'content': item.get('content', ''),
                        'bbox': item.get('bbox', [0, 0, 0, 0]),
                    }]
                }]
        
        if item.get('label', '').lower() in ['text', 'title', 'list', 'index', 'abstract', 'ref_text', 'paragraph_title']:
            para_block.setdefault('lines', []).append({
                'spans': [{
                    'content': item.get('text', item.get('content', '')),
                    'bbox': item.get('bbox', [0, 0, 0, 0]),
                }]
            })
        
        # Handle different block types
        label_lower = item.get('label', '').lower()
        if label_lower in ['text', 'title', 'list', 'index', 'abstract', 'ref_text', 'paragraph_title']:
            para_block.setdefault('lines', []).append({
                'spans': [{
                    'content': item.get('text', item.get('content', '')),
                    'bbox': item.get('bbox', [0, 0, 0, 0]),
                }]
            })
        
        para_blocks.append(para_block)
    
    return {
        'page_idx': 0,  # Will be set per page
        'page_size': [200, 200],  # placeholder
        'para_blocks': para_blocks,
        'discarded_blocks': discarded_blocks,
        'page_idx': 0,  # Will be set per page
        'page_size': [200, 200],
    }


def process_pdf_to_markdown(pdf_path: str, output_dir: str, batch_analyzer, doc_stem: str):
    """Process a single PDF and convert to markdown."""
    import fitz
    import time
    import io
    from PIL import Image
    from pathlib import Path
    from mineru.backend.pipeline.pipeline_middle_json_mkcontent import union_make, MakeMode
    
    doc = fitz.open(pdf_path)
    page_results = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=200)
        img = pix.tobytes('png')
        
        from PIL import Image
        import io
        pil_img = Image.open(io.BytesIO(img))
        
        images_with_extra_info = [(pil_img, True, 'ch')]
        
        start = time.time()
        result = batch_analyzer([(pil_img, True, 'ch')])
        
        # Convert batch result to page_info format
        page_info = {
            'page_idx': page_num,
            'page_size': [200, 200],  # Will be updated with actual size
            'para_blocks': [],
            'discarded_blocks': [],
            'page_idx': page_num,
            'page_size': [200, 200],
        }
        
        if result and isinstance(result[0], list):
            for item in result[0]:
                if not isinstance(item, dict):
                    continue
                    
                label = item.get('label', '')
                block_type = label_to_blocktype(item.get('label', ''))
                
                para_block = {
                    'type': label_to_blocktype(label),
                    'bbox': item.get('bbox', [0, 0, 0, 0]),
                    'score': item.get('score', 0.0),
                    'index': item.get('index', 0),
                }
                
                # Add text content if available
                if 'text' in item or 'content' in item:
                    text_content = item.get('text', item.get('content', ''))
                    para_block['lines'] = [{
                        'spans': [{
                            'content': item.get('text', item.get('content', '')),
                            'bbox': item.get('bbox', [0, 0, 0, 0]),
                        }]
                    }]
                
                # Add lines for text-like blocks
                label_lower = item.get('label', '').lower()
                if label_lower in ['text', 'title', 'list', 'index', 'abstract', 'ref_text', 'paragraph_title', 'caption', 'footer', 'header', 'ref_text', 'ref_text', 'table_caption', 'chart_caption', 'algorithm_caption', 'code_caption', 'image_caption', 'footnote', 'table_footnote', 'chart_caption', 'caption']:
                    text_content = item.get('text', item.get('content', ''))
                    para_block['lines'] = [{
                        'spans': [{
                            'content': text_content,
                            'bbox': item.get('bbox', [0, 0, 0, 0]),
                        }]
                    }]
                
                # Add type field for union_make
                para_block['type'] = label_lower_to_blocktype(label_lower)
                
                para_blocks.append(para_block)
        
        page_info = {
            'page_idx': page_num,
            'page_size': [200, 200],
            'para_blocks': para_blocks,
            'discarded_blocks': [],
            'page_idx': page_num,
            'page_size': [200, 200],
        }
        
        # Convert to markdown
        md = union_make([page_info], 'mm_markdown', 'images')
        
        # Save markdown
        output_path = Path(output_dir) / f"{Path(pdf_path).stem}.md"
        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)
        output_path.write_text(md, encoding='utf-8')
        
        print(f'  Saved: {output_path}')
    
    doc.close()


def label_to_blocktype(label: str) -> str:
    """Convert label to BlockType string for union_make."""
    label_lower = label.lower().replace(' ', '_').replace('-', '_')
    return LABEL_TO_BLOCKTYPE.get(label_lower, 'text')


def label_lower_to_blocktype(label_lower: str) -> str:
    """Convert label to BlockType string for union_make."""
    return LABEL_TO_BLOCKTYPE.get(label_lower, 'text')


def main():
    # Monkey patch HybridModelSingleton.get_model
    from mineru.backend.pipeline.model_init import HybridModelSingleton
    original_get_model = HybridModelSingleton.get_model
    def patched_get_model(self, lang=None, formula_enable=None, table_enable=None):
        return original_get_model(self, lang=lang, formula_enable=formula_enable)
    HybridModelSingleton.get_model = patched_get_model

    # Initialize model manager
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

    # Input and output directories
    input_root = Path('benchmark/golden_raw')
    output_root = Path('benchmark/golden')
    output_root.mkdir(parents=True, exist_ok=True)

    # Process each category
    categories = ['listed_company', 'industry_deep', 'unlisted_company', 'earnings_notes', 'decision_memo', 'unlisted_company']
    
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
        
        for pdf_file in pdf_files:
            try:
                process_pdf_to_markdown(str(pdf_file), str(output_dir), batch_analyzer, pdf_file.stem)
            except Exception as e:
                print(f'Error processing {pdf_file}: {e}')
                continue

    print('\n=== Batch conversion complete ===')


if __name__ == '__main__':
    main()
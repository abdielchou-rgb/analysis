# -*- coding: utf-8 -*-
import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
p = r'D:\2hao-analyst\output\柯力传感深度分析报告_v5_20260804.md'
text = open(p, encoding='utf-8').read()

targets = ['三、产业周期与产品市场渗透分析', '四、问题与困境、优势与机遇', '六、发展方向、规划路径与商业打法']
for t in targets:
    idx = text.find(t)
    if idx == -1:
        print(f"NOT FOUND: {t}")
        continue
    # 找下一章节标题
    nxt = re.search(r'\n## ', text[idx+len(t):])
    end = idx + len(t) + nxt.start() if nxt else len(text)
    print("="*90)
    print(text[idx:end][:3500])

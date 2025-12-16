"""Fix column mappings in data_sources.yml"""
import re

# Read file
with open('config/data_sources.yml', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 计划名称 -> 计划全称
content = content.replace(
    '            target: "计划名称"\r\n            optional: true',
    '            target: "计划全称"  # Fixed: actual column name\r\n            optional: true'
)

# Also try Unix line endings
content = content.replace(
    '            target: "计划名称"\n            optional: true',
    '            target: "计划全称"  # Fixed: actual column name\n            optional: true'
)

# Fix 资格 -> 管理资格
content = content.replace(
    '            target: "资格"\r\n            optional: true',
    '            target: "管理资格"  # Fixed: actual column name\r\n            optional: true'
)

content = content.replace(
    '            target: "资格"\n            optional: true',
    '            target: "管理资格"  # Fixed: actual column name\n            optional: true'
)

# Write back
with open('config/data_sources.yml', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed column mappings in data_sources.yml')

import os
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

# API配置
API_KEY = os.getenv('API_KEY')
BASE_URL = os.getenv('BASE_URL')
MODEL = os.getenv('MODEL')

# 文件处理配置
FILE_DELETE_DELAY = int(os.getenv('FILE_DELETE_DELAY', 300))  # 默认5分钟
MLM_PROMPT = os.getenv('PROMPT')

# PDF处理相关配置
PDF_CONCURRENT_LIMIT = int(os.getenv('PDF_CONCURRENT_LIMIT', '5'))
PDF_BATCH_SIZE = int(os.getenv('PDF_BATCH_SIZE', '10'))

# 验证必需的环境变量
required_vars = ['API_KEY', 'BASE_URL', 'MODEL', 'PROMPT']
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
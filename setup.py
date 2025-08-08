from distutils.core import setup
from setuptools import find_packages

with open("README.md", "r") as f:
    long_description = f.read()

setup(name='jupiter-nacos-client',  # 包名
      version='1.0.4',  # 版本号
      description='Simple nacos client package',
      long_description=long_description,
      long_description_content_type='text/markdown',
      author='tkiyer',
      author_email='jiyidexin@yeah.net',
      url='https://github.com/JupiterData-AI/jupiter-nacos-python',
      install_requires=[
          'requests', 'fastapi', 'uvicorn', 'nacos-sdk-python', 'python-dotenv', 'circuitbreaker',
          'pydantic'
      ],
      python_requires='>=3.7',
      license='Apache License',
      packages=find_packages(),
      platforms=["all"],
      )
import os
import pandas as pd
import pdfplumber

from abc import ABC, abstractmethod


class AbstractReader(ABC):
    def __init__(self):
        # 初始化代码，例如设置日志等
        pass

    @abstractmethod
    def read(self, file_path):
        """
        根据文件后缀格式读取文件数据并返回对应dataframe结构数据，需要在子类中实现。

        :param file_path: 待读取的数据文件
        :return: dataframe结构数据
        """
        pass

    # 可以添加其他共有的方法或属性


class CSVReader(AbstractReader):
    def read(
        self,
        file_path,
        delimiter=",",
        encoding="utf-8-sig",
        strip_columns=True,
        **kwargs,
    ):
        df = pd.read_csv(file_path, delimiter=delimiter, encoding=encoding, **kwargs)
        if strip_columns:
            df = df.rename(columns=str.strip)
        return df


class ExcelReader(AbstractReader):
    def read(
        self,
        file_path,
        sheet_name=0,
        header=0,
        usecols=None,
        dtype=None,
        skiprows=None,
        **kwargs,
    ):
        return pd.read_excel(
            file_path,
            sheet_name=sheet_name,
            header=header,
            usecols=usecols,
            dtype=dtype,
            skiprows=skiprows,
            **kwargs,
        )


class PDFReader(AbstractReader):
    def read(self, file_path):
        # 读取 PDF 文件并将其转换为文本
        with pdfplumber.open(file_path) as pdf:
            pages = [page.extract_text() for page in pdf.pages]
        # 可根据实际需求进一步处理 PDF 文本
        return pages  # 这里返回的是 PDF 文本的列表，每个元素代表一页


class TextReader(AbstractReader):
    def read(self, file_path, encoding="utf-8", sep="\n", **kwargs):
        with open(file_path, "r", encoding=encoding) as file:
            text = file.read().split(sep)
        return text  # 返回按行分割的文本列表


if __name__ == "__main__":
    reader = ExcelReader()
    data = reader.read(
        file_path=r"D:\Share\DATABASE\数据更新\Daily Update\保险考核业绩2019版_渠道.xlsx",
        header=3,
    )
    print(data)

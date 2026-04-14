from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from app.parsers.linux_default_parser import LinuxDefaultParser
from app.parsers.xray_collector_parser import XrayCollectorParser


ProductType = Literal["xray", "unknown"]


class AnalyzerParser(Protocol):
    parser_name: str
    parser_version: str

    def parse(
        self,
        *,
        task_id: str,
        analysis_root: Path,
        archive_name: str | None = None,
        archive_size_bytes: int | None = None,
    ): ...


@dataclass(frozen=True)
class RoutedParser:
    product_type: ProductType
    parser_id: str
    parser: AnalyzerParser


@dataclass(frozen=True)
class ProductRouter:
    xray_parser: XrayCollectorParser = XrayCollectorParser()
    linux_parser: LinuxDefaultParser = LinuxDefaultParser()

    def detect_product_type(self, analysis_root: Path) -> ProductType:
        if self.xray_parser.detect(analysis_root) is not None:
            return "xray"
        return "unknown"

    def route(self, analysis_root: Path) -> RoutedParser:
        product_type = self.detect_product_type(analysis_root)
        if product_type == "xray":
            return RoutedParser(
                product_type="xray",
                parser_id="xray-collector-parser",
                parser=self.xray_parser,
            )

        return RoutedParser(
            product_type="unknown",
            parser_id="linux-default-parser",
            parser=self.linux_parser,
        )

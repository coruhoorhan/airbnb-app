#!/usr/bin/env python3
"""
Magda-Agent Universal Codebase AST & Symbol Indexer.
Generic entry point for ANY project repository.
"""

from magda_airbnb_codebase_indexer import AirbnbCodebaseIndexer

class UniversalCodebaseIndexer(AirbnbCodebaseIndexer):
    """Universal AST and Symbol Indexer for web applications."""
    pass

if __name__ == "__main__":
    from magda_airbnb_codebase_indexer import main
    main()

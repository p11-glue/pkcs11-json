#!/usr/bin/python

"""
SPDX-License-Identifier: BSD-3-Clause
"""

import json
import sys
import xml.etree.ElementTree as ET


class Type:
    def __init__(self, el, types, aliases):
        self.el = el
        self.types = types
        self.aliases = aliases

    def resolve(self):
        raise NotImplementedError

    def resolve_ffi_type(self):
        raise NotImplementedError


class Typedef(Type):
    def resolve(self):
        return self.el.get("name")

    def resolve_ffi_type(self):
        return self.types[self.el.get("type")].resolve_ffi_type()


class PointerType(Type):
    def resolve(self):
        alias = self.aliases.get(self.el.get('id'))
        if alias is not None:
            return alias
        else:
            return f"{self.types[self.el.get('type')].resolve()} *"

    def resolve_ffi_type(self):
        return "pointer"


class FundamentalType(Type):
    def resolve(self):
        return self.el.get("name")

    def resolve_ffi_type(self):
        if self.el.get("size") == "8":
            return "uchar"
        elif self.el.get("size") == "64":
            return "ulong"


class CvQualifiedType(Type):
    def resolve(self):
        return f"const {self.types[self.el.get('type')].resolve()}"


class ElaboratedType(Type):
    def resolve(self):
        keyword = self.el.get("keyword")
        if keyword == "struct":
            return self.types[self.el.get('type')].resolve()
        else:
            raise NotImplementedError


class ArrayType(Type):
    def resolve(self):
        return (f"{self.types[self.el.get('type')].resolve()}"
                f"[{self.el.get('max')}]")


class Struct(Type):
    def resolve(self):
        return f"struct {self.el.get('name')}"


class FunctionType(Type):
    pass


TYPES = [
    "Typedef",
    "PointerType",
    "FundamentalType",
    "ElaboratedType",
    "CvQualifiedType",
    "ArrayType",
    "FunctionType",
    "Struct",
]


class Function(Type):
    def __init__(self, el, types, aliases):
        super().__init__(el, types, aliases)
        self.version = 2

    def to_json(self):
        obj = {}
        obj["name"] = self.el.get("name")
        obj["version"] = self.version
        returns = self.el.get("returns")
        obj["returns"] = self.types[returns].resolve()
        obj["arguments"] = []
        for arg in self.el.iter("Argument"):
            obj["arguments"].append({
                "type": self.types[arg.get("type")].resolve(),
                "name": arg.get("name"),
                "ffi-type": self.types[arg.get("type")].resolve_ffi_type(),
            })
        return obj


class FunctionEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Function):
            return obj.to_json()
        else:
            return super().default(obj)


class AST:
    def __init__(self, root):
        self.root = root
        types = {}
        aliases = {}
        functions = {}

        gil = self.root.find("./Function[@name='C_GetInterfaceList']")
        self.file = self.root.find(f'''./File[@id="{gil.get('file')}"]''')\
                             .get("name")

        for el in self.root.iter():
            if el.tag not in TYPES:
                continue
            cls = getattr(sys.modules[__name__], el.tag)
            if cls is None:
                continue
            types[el.get("id")] = cls(el, types, aliases)

        for el in self.root.iter("Typedef"):
            aliases[el.get("type")] = el.get("name")

        for el in self.root.iter("Function"):
            functions[el.get("name")] = Function(el, types, aliases)

        function_names2 = self.get_function_names(2)
        function_names3 = self.get_function_names(3)

        self.functions = []
        for name in function_names3:
            function = functions[name]
            if name not in function_names2:
                function.version = 3
            else:
                function.version = 2
            self.functions.append(function)

    def get_function_names(self, version):
        if version == 2:
            struct = self.root.find("./Struct[@name='_CK_FUNCTION_LIST']")
        else:
            struct = self.root.find("./Struct[@name='_CK_FUNCTION_LIST_3_0']")
        names = []
        for member in struct.get("members").split(" ")[1:]:
            el = self.root.find(f"./Field[@id='{member}']")
            names.append(el.get("name"))
        return names


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("infile", type=argparse.FileType("r"))
    parser.add_argument("outfile", type=argparse.FileType("w"))
    args = parser.parse_args()

    tree = ET.parse(args.infile)
    root = tree.getroot()
    ast = AST(root)
    args.outfile.write(json.dumps({
        "comment": f"This file is automatically generated from {ast.file}",
        "license": "BSD-3-Clause",
        "functions": ast.functions
    },
                     cls=FunctionEncoder, indent=2))
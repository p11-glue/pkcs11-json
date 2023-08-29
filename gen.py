#!/usr/bin/python

"""
SPDX-License-Identifier: BSD-3-Clause
"""

from typing import Any, Mapping
import json
import subprocess
import sys
import xml.etree.ElementTree as ET


class Type:
    def __init__(self,
                 el,
                 types: Mapping[str, Any],
                 aliases: Mapping[str, str]):
        self.el = el
        self.types = types
        self.aliases = aliases

    def resolve(self) -> str:
        raise NotImplementedError

    def resolve_ffi_type(self) -> str:
        raise NotImplementedError


class Typedef(Type):
    def resolve(self) -> str:
        return self.el.get("name")

    def resolve_ffi_type(self) -> str:
        return self.types[self.el.get("type")].resolve_ffi_type()


class PointerType(Type):
    def resolve(self) -> str:
        alias = self.aliases.get(self.el.get('id'))
        if alias is not None:
            return alias
        else:
            return f"{self.types[self.el.get('type')].resolve()} *"

    def resolve_ffi_type(self) -> str:
        return "pointer"


class FundamentalType(Type):
    def resolve(self) -> str:
        return self.el.get("name")

    def resolve_ffi_type(self) -> str:
        if self.el.get("size") == "8":
            return "uchar"
        elif self.el.get("size") == "64":
            return "ulong"
        else:
            raise NotImplementedError


class CvQualifiedType(Type):
    def resolve(self) -> str:
        return f"const {self.types[self.el.get('type')].resolve()}"


class ElaboratedType(Type):
    def resolve(self) -> str:
        keyword = self.el.get("keyword")
        if keyword == "struct":
            return self.types[self.el.get('type')].resolve()
        else:
            raise NotImplementedError


class ArrayType(Type):
    def resolve(self) -> str:
        return (f"{self.types[self.el.get('type')].resolve()}"
                f"[{int(self.el.get('max')) + 1}]")


class Field(Type):
    def to_json(self) -> Mapping[str, Any]:
        obj = {}
        obj["name"] = self.el.get("name")
        obj["type"] = self.types[self.el.get("type")].resolve()
        return obj
    

class Struct(Type):
    def __init__(self,
                 el,
                 types: Mapping[str, Type],
                 aliases: Mapping[str, str]):
        super().__init__(el, types, aliases)
        self.members = []

    def resolve(self) -> str:
        alias = self.aliases.get(self.el.get('id'))
        if alias is not None:
            return alias
        else:
            return f"struct {self.el.get('name')}"

    def to_json(self) -> Mapping[str, Any]:
        obj = {}
        alias = self.aliases.get(self.el.get('id'))
        if alias is not None:
            obj["name"] = alias
        else:
            obj["name"] = self.el.get("name")
        obj["members"] = self.members
        return obj


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
    def __init__(self,
                 el,
                 types: Mapping[str, Type],
                 aliases: Mapping[str, str]):
        super().__init__(el, types, aliases)
        self.version = 2

    def to_json(self) -> Mapping[str, Any]:
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


class Encoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "to_json"):
            return obj.to_json()
        else:
            return super().default(obj)


class AST:
    def __init__(self, root):
        self.root = root
        types = {}
        aliases = {}
        functions = {}
        self.structs = []

        gil = self.root.find("./Function[@name='C_GetInterfaceList']")
        self.origin = self.root.find(f'''./File[@id="{gil.get('file')}"]''')\
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

        for el in self.root.iter("ElaboratedType"):
            alias = aliases.get(el.get("id"))
            if alias is not None:
                aliases[el.get("type")] = alias

        for el in self.root.iter("Struct"):
            if el.get("incomplete") == "1":
                continue

            name = aliases.get(el.get("id"), el.get("name"))
            if not name.startswith("CK_"):
                continue

            struct = Struct(el, types, aliases)

            struct.members = [
                Field(self.root.find(f"./Field[@id='{member}']"),
                      types, aliases)
                for member in el.get("members", "").split(" ")
            ]

            self.structs.append(struct)

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
    parser.add_argument("--castxml-program", required=False, default="castxml")
    parser.add_argument("-o", "--outfile", type=argparse.FileType("w"),
                        required=False, default=sys.stdout)
    args = parser.parse_args()

    castxml = subprocess.run([args.castxml_program,
                              "--castxml-output=1", "-o", "-",
                              args.infile.name], capture_output=True)
    root = ET.fromstring(castxml.stdout)
    ast = AST(root)
    args.outfile.write(json.dumps({
        "comment": f"This file is automatically generated from {ast.origin}",
        "license": "BSD-3-Clause",
        "functions": ast.functions,
        "structs": ast.structs,
    },
                                  cls=Encoder, indent=2))
    args.outfile.write("\n")

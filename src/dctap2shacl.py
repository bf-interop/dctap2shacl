import csv
import pathlib

import rdflib

from dataclasses import dataclass, field
from typing import Union


BF = rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")
BFLC = rdflib.Namespace("http://id.loc.gov/ontologies/bflc/")

# dctap column naming the alternatives of a property that expects a different
# valueNodeType, see https://github.com/bf-interop/dctap2shacl/issues/7
OR_COLUMNS = ("sh:or", "sh_or")

NODE_TYPE_ALIASES = {
    "blank node": "bnode",
    "blanknode": "bnode",
    "uri": "iri",
}

NODE_KINDS = {
    frozenset({"literal"}): rdflib.SH.Literal,
    frozenset({"iri"}): rdflib.SH.IRI,
    frozenset({"bnode"}): rdflib.SH.BlankNode,
    frozenset({"bnode", "iri"}): rdflib.SH.BlankNodeOrIRI,
    frozenset({"iri", "literal"}): rdflib.SH.IRIOrLiteral,
    frozenset({"bnode", "literal"}): rdflib.SH.BlankNodeOrLiteral,
}


def init_shacl() -> rdflib.Graph:
    graph = rdflib.Graph()
    graph.namespace_manager.bind("bf", BF)
    graph.namespace_manager.bind("bflc", BFLC)
    return graph


def prop_id_to_rdf_node(property_id):
    if ":" in property_id:
        namespace, suffix = property_id.split(":", 1)
        namespace = namespace.strip()
        suffix = suffix.strip()
        match namespace:
            case "bf":
                path_object = getattr(BF, suffix)

            case "bflc":
                path_object = getattr(BFLC, suffix)

            case "rdf":
                path_object = getattr(rdflib.RDF, suffix)

            case "rdfs":
                path_object = getattr(rdflib.RDFS, suffix)

            case _:
                path_object = rdflib.URIRef(property_id)

    elif property_id.startswith("http"):
        path_object = rdflib.URIRef(property_id)

    else:
        path_object = rdflib.Literal(property_id)

    return path_object


def split_column(value: Union[str, None]) -> list[str]:
    """Splits a semi-colon delimited dctap cell into its trimmed values"""
    if not value:
        return []
    return [entry.strip() for entry in value.split(";") if entry.strip()]


def property_ids(row: dict) -> list[str]:
    """Returns the one-or-more propertyIDs in a dctap row"""
    return split_column(row.get("propertyID"))


def or_alternatives(row: dict) -> list[str]:
    """Returns the alternative propertyIDs from a dctap row's sh:or column"""
    for column in OR_COLUMNS:
        alternatives = split_column(row.get(column))
        if alternatives:
            return alternatives
    return []


def or_shape_id(shape_id: str, root_property: str) -> rdflib.URIRef:
    """
    Returns the URI of the node shape that carries one group's SHACL or.

    A SHACL or result takes its severity from the shape holding the sh:or, not
    from the branches in its list, so every group needs a node shape of its own
    to keep the severity its dctap rows asked for. Hanging several sh:or on one
    shape also collapses them into a single validation result that names every
    branch of every group.
    """
    return rdflib.URIRef(f"{shape_id}:or:{root_property}")


def group_or_rows(dctap_rows: list[dict]) -> tuple[dict, dict]:
    """
    Groups dctap rows that name each other in the sh:or column.

    Alternatives are usually declared reciprocally, each row naming the other,
    and the paired rows are not always adjacent. Grouping therefore happens
    before any row is added to the graph so that a pair collapses into a single
    SHACL or instead of one per row.

    Returns the groups keyed by a (shapeID, propertyID) root, each holding the
    shape and an ordered mapping of propertyID to the row it came from, along
    with a mapping of row position to the group that row belongs to.
    """
    parents: dict[tuple[str, str], tuple[str, str]] = {}

    def find(key):
        parents.setdefault(key, key)
        while parents[key] != key:
            parents[key] = parents[parents[key]]
            key = parents[key]
        return key

    def union(left, right):
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    for row in dctap_rows:
        alternatives = or_alternatives(row)
        own_properties = property_ids(row)
        if not alternatives or not own_properties:
            continue
        shape_id = row.get("shapeID") or ""
        keys = [(shape_id, prop) for prop in own_properties + alternatives]
        for key in keys[1:]:
            union(keys[0], key)

    groups: dict = {}
    row_groups: dict[int, tuple[str, str]] = {}
    for position, row in enumerate(dctap_rows):
        shape_id = row.get("shapeID") or ""
        own_properties = property_ids(row)
        group_key = None
        for prop in own_properties:
            if (shape_id, prop) in parents:
                group_key = find((shape_id, prop))
                break
        if group_key is None:
            continue
        group = groups.setdefault(
            group_key,
            {"shape_id": shape_id, "root_property": group_key[1], "branches": {}},
        )
        for prop in own_properties:
            group["branches"][prop] = row
        for prop in or_alternatives(row):
            group["branches"].setdefault(prop, None)
        row_groups[position] = group_key

    for group in groups.values():
        dangling = [prop for prop, row in group["branches"].items() if row is None]
        if dangling:
            raise ValueError(
                f"{group['shape_id']} names {', '.join(dangling)} in its sh:or column "
                "without a dctap row of its own"
            )

    return groups, row_groups


@dataclass
class DCTap2SHACLTransformer:
    dctap: list[dict] = field(default_factory=list)
    graph: rdflib.Graph = field(default_factory=init_shacl)

    def set_mandatory(self, bnode: rdflib.BNode, mandatory: Union[str, None]):
        if mandatory and mandatory.strip().casefold().startswith("true"):
            self.graph.add((bnode, rdflib.SH.minCount, rdflib.Literal(1)))

    def set_repeatable(self, bnode: rdflib.BNode, repeatable: Union[str, None]):
        if repeatable and repeatable.strip().casefold().startswith("false"):
            self.graph.add((bnode, rdflib.SH.maxCount, rdflib.Literal(1)))

    def set_value_shape(self, bnode: rdflib.BNode, value_shape: Union[str, None]):
        if isinstance(value_shape, str) and len(value_shape.strip()) > 0:
            self.graph.add((bnode, rdflib.SH.node, rdflib.URIRef(value_shape)))

    def sh_datatype(self, datatype: str, property_bnode: rdflib.BNode):
        """Adds a rdflib.SH datatype to a property shape"""
        match datatype:
            case "rdf:langString":
                self.graph.add(
                    (property_bnode, rdflib.SH.datatype, rdflib.RDF.langString)
                )

            case "xsd:string":
                self.graph.add((property_bnode, rdflib.SH.datatype, rdflib.XSD.string))

    def sh_node_kind(
        self, property_bnode: rdflib.BNode, value_node_type: Union[str, None]
    ):
        """Adds a SHACL nodeKind to a property shape from a dctap valueNodeType"""
        node_types = {entry.casefold() for entry in split_column(value_node_type)}
        node_types = {NODE_TYPE_ALIASES.get(entry, entry) for entry in node_types}
        node_kind = NODE_KINDS.get(frozenset(node_types))
        if node_kind:
            self.graph.add((property_bnode, rdflib.SH.nodeKind, node_kind))

    def apply_row_constraints(
        self, property_bnode: rdflib.BNode, row: dict, include_severity: bool = True
    ):
        """
        Adds all of a dctap row's constraints to a property shape.

        Branches of a SHACL or pass include_severity as False. A branch severity
        is never reported, since the sh:or result carries the severity of the
        shape holding it, and a branch that fails only at sh:Warning counts as
        conforming while validating with warnings allowed, which silently
        satisfies the whole or and hides the group's own warning.
        """
        if include_severity:
            self.sh_severity(property_bnode, row.get("severity"))
        self.set_mandatory(property_bnode, row.get("mandatory"))
        self.set_repeatable(property_bnode, row.get("repeatable"))
        self.set_value_shape(property_bnode, row.get("valueShape"))
        self.sh_node_kind(property_bnode, row.get("valueNodeType"))

        if "valueDataType" in row:
            self.sh_datatype(row["valueDataType"], property_bnode)

    def add_or_shape(
        self, shape_id: str, root_property: str, row: dict
    ) -> rdflib.URIRef:
        """
        Adds the node shape that carries one group's SHACL or, targeting the
        same classes as the group's dctap row and holding its severity
        """
        or_shape = or_shape_id(shape_id, root_property)
        self.graph.add((or_shape, rdflib.RDF.type, rdflib.SH.NodeShape))
        if row.get("target") is not None:
            self.sh_targets(row, or_shape)
        self.sh_severity(or_shape, row.get("severity"))
        return or_shape

    def add_or_branch(self, property_id: str, row: dict) -> rdflib.BNode:
        """Adds one branch of a SHACL or as a property shape"""
        prop_bnode = rdflib.BNode()
        self.graph.add((prop_bnode, rdflib.RDF.type, rdflib.SH.PropertyShape))
        self.graph.add((prop_bnode, rdflib.SH.path, prop_id_to_rdf_node(property_id)))
        self.apply_row_constraints(prop_bnode, row, include_severity=False)
        return prop_bnode

    def sh_or_properites(self, row: dict):
        """
        Adds a SHACL OR using RDF list for a list of properites
        """
        properties = property_ids(row)
        or_shape = self.add_or_shape(row["shapeID"], properties[0], row)
        or_blank_node = rdflib.BNode()
        self.graph.add((or_shape, getattr(rdflib.SH, "or"), or_blank_node))
        items = [self.add_or_branch(prop, row) for prop in properties]
        rdflib.collection.Collection(self.graph, or_blank_node, items)

    def sh_or_alternatives(self, group: dict):
        """
        Adds a SHACL OR using an RDF list for properties declared as
        alternatives of each other in the dctap sh:or column. Each branch keeps
        the constraints of the row it came from, which is what distinguishes
        this from sh_or_properites where every branch shares one row.
        """
        branches = group["branches"]
        root_property = group["root_property"]
        or_shape = self.add_or_shape(
            group["shape_id"], root_property, branches[root_property]
        )
        or_blank_node = rdflib.BNode()
        self.graph.add((or_shape, getattr(rdflib.SH, "or"), or_blank_node))
        items = []
        for property_id, row in branches.items():
            prop_bnode = self.add_or_branch(property_id, row)
            label = (row.get("propertyLabel") or "").strip()
            if label:
                self.graph.add((prop_bnode, rdflib.RDFS.label, rdflib.Literal(label)))
            items.append(prop_bnode)
        rdflib.collection.Collection(self.graph, or_blank_node, items)

    def sh_property_shape(self, shape_id: rdflib.Node, label: str) -> rdflib.BNode:
        """Adds rdflib.SH Property Shape"""
        property_bnode = rdflib.BNode()
        self.graph.add((shape_id, rdflib.SH.property, property_bnode))
        self.graph.add((property_bnode, rdflib.RDF.type, rdflib.SH.PropertyShape))
        self.graph.add((property_bnode, rdflib.RDFS.label, rdflib.Literal(label)))
        return property_bnode

    def sh_severity(self, property_bnode: rdflib.BNode, severity: Union[str, None]):
        """Checks and adds severity to property"""
        if severity:
            match severity.strip().casefold():
                case "violation":
                    severity_level = rdflib.SH.Violation

                case "warning":
                    severity_level = rdflib.SH.Warning

                case _:
                    severity_level = rdflib.SH.Info

            self.graph.add((property_bnode, rdflib.SH.severity, severity_level))

    def sh_targets(self, row: dict, shape_node: Union[rdflib.URIRef, None] = None):
        """Adds SHACL targets to graph"""
        targets = [
            prop_id_to_rdf_node(target) for target in split_column(row.get("target"))
        ]
        if shape_node is None:
            shape_node = rdflib.URIRef(row["shapeID"])
        for target in targets:
            self.graph.add((shape_node, rdflib.SH.targetClass, target))

    def sh_value_constaint(
        self,
        value_constraint: str,
        value_constraint_type: str,
        property_bnode: rdflib.BNode,
    ):
        """Adds a value constraint type to a property shape"""
        predicate = None
        match value_constraint_type:
            case "picklist" | "IRIstem" | "languageTag":
                pass

            case "pattern":
                predicate = rdflib.SH.pattern

            case "minLength":
                predicate = rdflib.SH.minLength

            case "maxLength":
                predicate = rdflib.SH.maxLength

            case "minInclusive":
                predicate = rdflib.SH.minInclusive

            case "maxInclusive":
                predicate = rdflib.SH.maxInclusive

        if predicate:
            self.graph.add(
                (property_bnode, predicate, rdflib.Literal(value_constraint))
            )

    def add_node_shape(self, row: dict) -> rdflib.URIRef:
        """Adds the row's shapeID as a rdflib.SH Node Shape if not already present"""
        shape_id = rdflib.URIRef(row["shapeID"])
        node_shape = self.graph.value(subject=shape_id, predicate=rdflib.RDF.type)
        if (
            node_shape is None
        ):  # rdflib.SH Node Shape not in graph, adds shape_id as a rdflib.SH graph
            self.graph.add((shape_id, rdflib.RDF.type, rdflib.SH.NodeShape))
            if len(row["shapeLabel"]) > 1:
                self.graph.add(
                    (shape_id, rdflib.RDFS.label, rdflib.Literal(row["shapeLabel"]))
                )
        return shape_id

    def add_property(self, row: dict):
        """Adds a rdflib.SH Node Property to the shape graph"""
        shape_id = self.add_node_shape(row)

        if ";" in row["propertyID"]:
            self.sh_or_properites(row)
            return

        property_bnode = self.sh_property_shape(shape_id, row["propertyLabel"])
        path_object = prop_id_to_rdf_node(row["propertyID"].strip())
        self.graph.add((property_bnode, rdflib.SH.path, path_object))
        self.apply_row_constraints(property_bnode, row)

    def generate_shacl(self, dctap_rows: list[dict]):
        """
        Takes a list of dictionaries from DCTap and creates SHACL validation graph
        """
        or_groups, row_groups = group_or_rows(dctap_rows)
        emitted = set()
        for position, row in enumerate(dctap_rows):
            if row.get("shapeID") is None:
                continue
            if row.get("target") is not None:
                self.sh_targets(row)

            group_key = row_groups.get(position)
            if group_key is None:
                self.add_property(row)
                continue
            if group_key in emitted:  # An earlier row already added this SHACL or
                continue
            self.add_node_shape(row)
            self.sh_or_alternatives(or_groups[group_key])
            emitted.add(group_key)

    def run(self, dctap_file: str):
        """
        Opens a dctap tsv file or textual string and transform to SHACL graph
        """
        dctap_path = pathlib.Path(dctap_file)
        if not dctap_path.exists():
            raise ValueError(f"{dctap_file} not found")
        with dctap_path.open() as fo:
            reader = csv.DictReader(fo, delimiter="\t")
            dctap_rows = [row for row in reader]
            self.generate_shacl(dctap_rows)

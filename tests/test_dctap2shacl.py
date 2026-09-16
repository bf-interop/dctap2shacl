import pytest

import rdflib

from dctap2shacl import DCTap2SHACLTransformer, BF, BFLC


def or_branches(graph: rdflib.Graph, shape_id: str) -> list:
    """Returns the property shapes in a shape's single SHACL or list"""
    shape_node = rdflib.URIRef(shape_id)
    or_nodes = list(
        graph.objects(subject=shape_node, predicate=getattr(rdflib.SH, "or"))
    )
    assert len(or_nodes) == 1, f"expected one sh:or on {shape_id}, got {len(or_nodes)}"
    return list(rdflib.collection.Collection(graph, or_nodes[0]))


def agent_or_rows() -> list[dict]:
    """Two alternatives that each name the other in the sh:or column"""
    return [
        {
            "shapeID": "big:ProvisionActivity",
            "shapeLabel": "Provision Activity",
            "propertyID": "bflc:simpleAgent",
            "propertyLabel": "Agent Simple Label",
            "valueShape": "",
            "mandatory": "true",
            "severity": "Violation",
            "valueNodeType": "literal",
            "repeatable": "true",
            "sh:or": "bf:agent",
        },
        {
            "shapeID": "big:ProvisionActivity",
            "shapeLabel": "Provision Activity",
            "propertyID": "bf:agent",
            "propertyLabel": "Agent",
            "valueShape": "big:Agent",
            "mandatory": "true",
            "severity": "Violation",
            "valueNodeType": "IRI ; bnode",
            "repeatable": "true",
            "sh:or": "bflc:simpleAgent",
        },
    ]


@pytest.fixture
def bf_instance_print_row():
    return {
        "shapeID": "big:Monograph:Instance:Print",
        "shapeLabel": "Instance (Monograph) Print",
        "target": "bf:Print",
        "propertyID": "bf:instanceOf",
        "propertyLabel": "Instance of",
        "valueShape": "big:Monograph:Work",
        "mandatory": "true",
        "severity": "Violation",
        "valueNodeType": "IRI; bnode",
        "repeatable": "true",
    }


def test_add_property(bf_instance_print_row):
    transformer = DCTap2SHACLTransformer()
    transformer.add_property(bf_instance_print_row)
    big_monograph_instance = rdflib.URIRef("big:Monograph:Instance:Print")
    assert (
        transformer.graph.value(
            subject=big_monograph_instance, predicate=rdflib.RDF.type
        )
        == rdflib.SH.NodeShape
    )
    assert transformer.graph.value(
        subject=big_monograph_instance, predicate=rdflib.RDFS.label
    ) == rdflib.Literal("Instance (Monograph) Print")
    property_instanceOf = transformer.graph.value(
        subject=big_monograph_instance, predicate=rdflib.SH.property
    )
    assert (
        transformer.graph.value(subject=property_instanceOf, predicate=rdflib.RDF.type)
        == rdflib.SH.PropertyShape
    )
    assert transformer.graph.value(
        subject=property_instanceOf, predicate=rdflib.RDFS.label
    ) == rdflib.Literal("Instance of")
    assert transformer.graph.value(
        subject=property_instanceOf, predicate=rdflib.SH.node
    ) == rdflib.URIRef("big:Monograph:Work")
    assert transformer.graph.value(
        subject=property_instanceOf, predicate=rdflib.SH.minCount
    ) == rdflib.Literal(1)
    assert (
        transformer.graph.value(subject=property_instanceOf, predicate=rdflib.SH.path)
        == BF.instanceOf
    )
    assert (
        transformer.graph.value(
            subject=property_instanceOf, predicate=rdflib.SH.severity
        )
        == rdflib.SH.Violation
    )
    assert (
        transformer.graph.value(
            subject=property_instanceOf, predicate=rdflib.SH.nodeKind
        )
        == rdflib.SH.BlankNodeOrIRI
    )


def test_shacl_or_property_id():
    role_row = {
        "shapeID": "big:Role",
        "shapeLabel": "Role",
        "target": "bf:Role",
        "propertyID": "rdfs:label ; bf:code",
        "propertyLabel": "Role Label",
        "valueShape": "big:AdminMetadata",
        "mandatory": "true",
        "severity": "Warning",
        "valueNodeType": "literal",
        "repeatable": "true",
    }
    transformer = DCTap2SHACLTransformer()
    transformer.add_property(role_row)

    assert len(transformer.graph) == 17
    shape_node = rdflib.URIRef("big:Role")
    or_blank_node = transformer.graph.value(
        subject=shape_node, predicate=getattr(rdflib.SH, "or")
    )
    or_collection = rdflib.collection.Collection(transformer.graph, or_blank_node)
    assert len(or_collection) == 2
    assert (
        transformer.graph.value(subject=or_collection[0], predicate=rdflib.SH.path)
        == rdflib.RDFS.label
    )
    assert transformer.graph.value(
        subject=or_collection[0], predicate=rdflib.SH.minCount
    ) == rdflib.Literal(1)
    assert (
        transformer.graph.value(subject=or_collection[1], predicate=rdflib.SH.path)
        == BF.code
    )
    assert (
        transformer.graph.value(subject=or_collection[1], predicate=rdflib.SH.maxCount)
        is None
    )


@pytest.mark.parametrize(
    "value_node_type,expected",
    [
        ("literal", rdflib.SH.Literal),
        ("IRI", rdflib.SH.IRI),
        ("bnode", rdflib.SH.BlankNode),
        ("IRI ; bnode", rdflib.SH.BlankNodeOrIRI),
        ("literal; IRI", rdflib.SH.IRIOrLiteral),
        ("blank node ; literal", rdflib.SH.BlankNodeOrLiteral),
        ("", None),
        (None, None),
        ("IRI; bnode; literal", None),
        ("wibble", None),
    ],
)
def test_sh_node_kind(value_node_type, expected):
    transformer = DCTap2SHACLTransformer()
    property_bnode = rdflib.BNode()
    transformer.sh_node_kind(property_bnode, value_node_type)

    assert (
        transformer.graph.value(subject=property_bnode, predicate=rdflib.SH.nodeKind)
        == expected
    )


def test_sh_or_column_reciprocal():
    transformer = DCTap2SHACLTransformer()
    transformer.generate_shacl(agent_or_rows())

    branches = or_branches(transformer.graph, "big:ProvisionActivity")
    assert len(branches) == 2

    # Neither alternative may be emitted as a standalone, independently
    # required, property shape
    assert (
        len(
            list(
                transformer.graph.objects(
                    subject=rdflib.URIRef("big:ProvisionActivity"),
                    predicate=rdflib.SH.property,
                )
            )
        )
        == 0
    )

    simple_agent, agent = branches
    assert (
        transformer.graph.value(subject=simple_agent, predicate=rdflib.SH.path)
        == BFLC.simpleAgent
    )
    assert transformer.graph.value(
        subject=simple_agent, predicate=rdflib.RDFS.label
    ) == rdflib.Literal("Agent Simple Label")
    assert (
        transformer.graph.value(subject=simple_agent, predicate=rdflib.SH.nodeKind)
        == rdflib.SH.Literal
    )
    assert transformer.graph.value(
        subject=simple_agent, predicate=rdflib.SH.minCount
    ) == rdflib.Literal(1)
    assert (
        transformer.graph.value(subject=simple_agent, predicate=rdflib.SH.node) is None
    )

    assert transformer.graph.value(subject=agent, predicate=rdflib.SH.path) == BF.agent
    assert transformer.graph.value(
        subject=agent, predicate=rdflib.RDFS.label
    ) == rdflib.Literal("Agent")
    assert (
        transformer.graph.value(subject=agent, predicate=rdflib.SH.nodeKind)
        == rdflib.SH.BlankNodeOrIRI
    )
    assert transformer.graph.value(
        subject=agent, predicate=rdflib.SH.node
    ) == rdflib.URIRef("big:Agent")


def test_sh_or_column_non_adjacent():
    rows = agent_or_rows()
    unrelated = dict(rows[0])
    unrelated.update({"propertyID": "bf:note", "propertyLabel": "Note", "sh:or": ""})
    transformer = DCTap2SHACLTransformer()
    transformer.generate_shacl([rows[0], unrelated, rows[1]])

    # The pair still collapses into one sh:or despite the row in between
    branches = or_branches(transformer.graph, "big:ProvisionActivity")
    assert len(branches) == 2

    # and the unrelated row keeps its own property shape
    note_shape = transformer.graph.value(
        subject=rdflib.URIRef("big:ProvisionActivity"), predicate=rdflib.SH.property
    )
    assert (
        transformer.graph.value(subject=note_shape, predicate=rdflib.SH.path) == BF.note
    )


def test_sh_or_column_one_sided():
    rows = agent_or_rows()
    transformer = DCTap2SHACLTransformer()
    transformer.generate_shacl([rows[0]])

    branches = or_branches(transformer.graph, "big:ProvisionActivity")
    assert len(branches) == 2

    # bf:agent has no dctap row of its own so only its path is known
    dangling = branches[1]
    assert (
        transformer.graph.value(subject=dangling, predicate=rdflib.SH.path) == BF.agent
    )
    assert len(list(transformer.graph.predicate_objects(subject=dangling))) == 1


def test_run_dctap_or_column():
    transformer = DCTap2SHACLTransformer()
    transformer.run("tests/instance_monograph_or.tsv")

    shape_node = rdflib.URIRef("big:ProvisionActivity")
    or_nodes = list(
        transformer.graph.objects(
            subject=shape_node, predicate=getattr(rdflib.SH, "or")
        )
    )
    # One sh:or each for the agent, date and place alternatives
    assert len(or_nodes) == 3

    paths = set()
    for or_node in or_nodes:
        for branch in rdflib.collection.Collection(transformer.graph, or_node):
            paths.add(transformer.graph.value(subject=branch, predicate=rdflib.SH.path))
    assert paths == {
        BFLC.simpleAgent,
        BF.agent,
        BF.date,
        BFLC.simpleDate,
        BF.place,
        BFLC.simplePlace,
    }

    # The two rows without a sh:or value stay as ordinary property shapes
    property_paths = {
        transformer.graph.value(subject=property_shape, predicate=rdflib.SH.path)
        for property_shape in transformer.graph.objects(
            subject=shape_node, predicate=rdflib.SH.property
        )
    }
    assert property_paths == {BF.mainTitle, BF.note}

    # A blank target cell must not become a targetClass
    assert rdflib.Literal("") not in set(
        transformer.graph.objects(subject=shape_node, predicate=rdflib.SH.targetClass)
    )


def test_run_dctap_csv():
    transformer = DCTap2SHACLTransformer()
    transformer.run("tests/admin_metadata.tsv")

    assert len(transformer.graph) == 19
    big_admin_metadata_shape = rdflib.URIRef("big:AdminMetadata")

    assert (
        transformer.graph.value(
            subject=big_admin_metadata_shape, predicate=rdflib.SH.targetClass
        )
        == BF.AdminMetadata
    )


def test_run_missing_dctap_csv():
    transformer = DCTap2SHACLTransformer()

    with pytest.raises(ValueError, match="bf-print.tsv not found"):
        transformer.run("bf-print.tsv")

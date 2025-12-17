import pytest

import rdflib

from dctap2shacl import DCTap2SHACLTransformer, BF


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

# Copyright 2018 by Embrapa.  All rights reserved.
#
# This code is part of the machado distribution and governed by its
# license. Please see the LICENSE.txt and README.md files that should
# have been included as part of this package for licensing information.

"""Coexpression."""

from machado.models import Organism
from machado.loaders.common import retrieve_feature
from machado.loaders.common import retrieve_ontology_term
from machado.loaders.feature import FeatureLoader
from machado.loaders.exceptions import ImportingError
from django.db.utils import IntegrityError


class CoexpressionLoader(object):
    """Load coexpression records."""

    help = 'Load coexpression records.'

    def __init__(self,
                 filename: str,
                 organism: Organism,
                 source: str = "LSTRAP_SOURCE",
                 value: str = None) -> None:
        """Execute the init function."""
        self.filename = filename
        self.value = value
        self.excluded = list()
        self.included = list()
        self.organism = organism

        # get cvterm for correlation
        self.cvterm_corel = retrieve_ontology_term(
            ontology='relationship',
            term='correlated with')
        self.cvterm_cluster = retrieve_ontology_term(
            ontology='relationship',
            term='in branching relationship with')
        self.featureloader = FeatureLoader(
                source=source,
                filename=self.filename,
                organism=self.organism)

    def store_coexpression_clusters(self,
                                    members: list) -> None:
        """Retrieve Feature objects and store in list and then store group."""
        try:
            for ident in members:
                # check features for id
                feature = retrieve_feature(featureacc=ident,
                                           organism=self.organism)
                if feature is not None:
                    self.included.append(feature)
                else:
                    self.excluded.append(ident)
        except IntegrityError as e:
            raise ImportingError(e)

        if len(self.included) > 1:
            try:
                self.featureloader.store_feature_relationships_group(
                        self.included,
                        term=self.cvterm_cluster,
                        value=self.value)
            except IntegrityError as e:
                raise ImportingError(e)

    def store_coexpression_pairs(self,
                                 members: list) -> None:
        """Retrieve Feature objects and store in list and then store group."""
        try:
            for ident in members:
                # check features for id
                feature = retrieve_feature(
                        featureacc=ident,
                        organism=self.organism)
                if feature is not None:
                    self.included.append(feature)
                else:
                    self.excluded.append(ident)
        except IntegrityError as e:
            raise ImportingError(e)

        if len(self.included) > 1:
            try:
                self.featureloader.store_feature_relationships_group(
                        group=self.included,
                        term=self.cvterm_corel,
                        value=self.value)
            except IntegrityError as e:
                raise ImportingError(e)
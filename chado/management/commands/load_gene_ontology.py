"""Load Gene Ontology."""

from chado.lib.cvterm import process_cvterm_xref
from chado.lib.cvterm import process_cvterm_go_synonym, process_cvterm_def
from chado.models import Cv, Cvterm, Cvtermprop, CvtermRelationship
from chado.models import CvtermDbxref, Db, Dbxref
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from multiprocessing import Lock
from obonet import read_obo
from tqdm import tqdm


class Command(BaseCommand):
    """Load Gene Ontology."""

    help = 'Load Gene Ontology'

    def add_arguments(self, parser):
        """Define the arguments."""
        parser.add_argument("--go", help="Gene Ontology file obo. Available "
                            "at http://www.geneontology.org/ontology/gene_ont"
                            "ology.obo", required=True, type=str)
        parser.add_argument("--cpu",
                            help="Number of threads",
                            default=1,
                            type=int)

    def store_type_def(self, typedef):
        """Store the type_def."""
        # Creating db internal to be used for creating dbxref objects
        db_internal, created = Db.objects.get_or_create(name='internal')

        # Creating dbxref is_transitive to be used for creating cvterms
        dbxref_is_transitive, created = Dbxref.objects.get_or_create(
            db=db_internal, accession='is_transitive')

        # Creating cv cvterm_property_type to be used for creating cvterms
        cv_cvterm_property_type, created = Cv.objects.get_or_create(
            name='cvterm_property_type')

        # Creating cvterm is_transitive to be used as type_id in cvtermprop
        cvterm_is_transitive, created = Cvterm.objects.get_or_create(
                cv=cv_cvterm_property_type,
                name='is_transitive',
                definition='',
                dbxref=dbxref_is_transitive,
                is_obsolete=0,
                is_relationshiptype=0)

        # Creating cvterm is_class_level to be used as type_id in cvtermprop
        dbxref_is_class_level, created = Dbxref.objects.get_or_create(
            db=db_internal, accession='is_class_level')

        cvterm_is_class_level, created = Cvterm.objects.get_or_create(
                cv=cv_cvterm_property_type,
                name='is_class_level',
                definition='',
                dbxref=dbxref_is_class_level,
                is_obsolete=0,
                is_relationshiptype=0)

        # Creating cvterm is_metadata_tag to be used as type_id in cvtermprop
        dbxref_is_metadata_tag, created = Dbxref.objects.get_or_create(
                db=db_internal, accession='is_metadata_tag')

        cvterm_is_metadata_tag, created = Cvterm.objects.get_or_create(
                cv=cv_cvterm_property_type,
                name='is_metadata_tag',
                definition='',
                dbxref=dbxref_is_metadata_tag,
                is_obsolete=0,
                is_relationshiptype=0)

        # Save the typedef to the Dbxref model
        db_global, created = Db.objects.get_or_create(name='_global')
        dbxref_typedef, created = Dbxref.objects.get_or_create(
            db=db_global,
            accession=typedef['id'],
            defaults={'description': typedef.get('def'),
                      'version': ''})

        # Save the typedef to the Cvterm model
        cv_sequence, created = Cv.objects.get_or_create(name='sequence')
        cvterm_typedef, created = Cvterm.objects.get_or_create(
            cv=cv_sequence,
            name=typedef.get('id'),
            is_obsolete=0,
            dbxref=dbxref_typedef,
            defaults={'definition': typedef.get('def'),
                      'is_relationshiptype': 1})

        # Load xref
        if typedef.get('xref_analog'):
            for xref in typedef.get('xref_analog'):
                process_cvterm_xref(cvterm_typedef, xref)

        # Load is_class_level
        if typedef.get('is_class_level') is not None:
            Cvtermprop.objects.get_or_create(
                    cvterm=cvterm_typedef,
                    type_id=cvterm_is_class_level.cvterm_id,
                    value=1,
                    rank=0)

        # Load is_metadata_tag
        if typedef.get('is_metadata_tag') is not None:
            Cvtermprop.objects.get_or_create(
                cvterm=cvterm_typedef,
                type_id=cvterm_is_metadata_tag.cvterm_id,
                value=1,
                rank=0)

        # Load is_transitive
        if typedef.get('is_transitive') is not None:
            Cvtermprop.objects.get_or_create(
                cvterm=cvterm_typedef,
                type_id=cvterm_is_transitive.cvterm_id,
                value=1,
                rank=0)

    def store_term(self, n, data, lock):
        """Store the ontology terms."""
        # Retrieving cvterm comment to be used as type_id in cvtermprop
        cv_cvterm_property_type, created = Cv.objects.get_or_create(
            name='cvterm_property_type')
        cvterm_comment = Cvterm.objects.get(cv=cv_cvterm_property_type,
                                            name='comment')

        # Save the term to the Dbxref model
        aux_db, aux_accession = n.split(':')
        db, created = Db.objects.get_or_create(name=aux_db)
        dbxref, created = Dbxref.objects.get_or_create(
            db=db, accession=aux_accession)

        # Save the term to the Cvterm model
        cv, created = Cv.objects.get_or_create(name=data.get('namespace'))
        cvterm, created = Cvterm.objects.get_or_create(
            cv=cv,
            name=data.get('name'),
            definition='',
            dbxref=dbxref,
            is_obsolete=0,
            is_relationshiptype=0)

        # Definitions usually contain recurrent dbxrefs
        # will sometimes break since they're running concurrently with
        # identical values. Locking this function call solved the problem.
        with lock:
            # Load definition and dbxrefs
            process_cvterm_def(cvterm, data.get('def'))

        # Load alt_ids
        if data.get('alt_id'):
            for alt_id in data.get('alt_id'):
                aux_db, aux_accession = alt_id.split(':')
                db_alt_id, created = Db.objects.get_or_create(name=aux_db)
                dbxref_alt_id, created = Dbxref.objects.get_or_create(
                    db=db_alt_id, accession=aux_accession)
                CvtermDbxref.objects.get_or_create(cvterm=cvterm,
                                                   dbxref=dbxref_alt_id,
                                                   is_for_definition=1)

        # Load comment
        if data.get('comment'):
            Cvtermprop.objects.get_or_create(
                cvterm=cvterm,
                type_id=cvterm_comment.cvterm_id,
                value=data.get('comment'),
                rank=0)

        # Load xref
        if data.get('xref_analog'):
            for xref in data.get('xref_analog'):
                process_cvterm_xref(cvterm, xref, 1)

        # Load synonyms
        for synonym_type in ('exact_synonym', 'related_synonym',
                             'narrow_synonym', 'broad_synonym'):
            if data.get(synonym_type):
                for synonym in data.get(synonym_type):
                    process_cvterm_go_synonym(cvterm, synonym,
                                              synonym_type)

    def store_relationship(self, u, v, type):
        """Store the relationship between ontology terms."""
        # retrieving term is_a to be used as type_id in cvterm_relationship
        cv_relationship, created = Cv.objects.get_or_create(
            name='relationship')
        cvterm_is_a = Cvterm.objects.get(cv=cv_relationship,
                                         name='is_a')

        # Get the subject cvterm
        subject_db_name, subject_dbxref_accession = u.split(':')
        subject_db, created = Db.objects.get_or_create(name=subject_db_name)
        subject_dbxref = Dbxref.objects.get(
            db=subject_db, accession=subject_dbxref_accession)
        subject_cvterm = Cvterm.objects.get(dbxref=subject_dbxref)

        # Get the object cvterm
        object_db_name, object_dbxref_accession = v.split(':')
        object_db, created = Db.objects.get_or_create(name=object_db_name)
        object_dbxref = Dbxref.objects.get(
            db=object_db, accession=object_dbxref_accession)
        object_cvterm = Cvterm.objects.get(dbxref=object_dbxref)

        # Get the relationship type
        if type == 'is_a':
            type_cvterm = cvterm_is_a
        else:
            type_db = Db.objects.get(name='_global')
            type_dbxref = Dbxref.objects.get(db=type_db,
                                             accession=type)
            type_cvterm = Cvterm.objects.get(dbxref=type_dbxref)

        # Save the relationship to the CvtermRelationship model
        cvrel = CvtermRelationship.objects.create(
            type_id=type_cvterm.cvterm_id,
            subject_id=subject_cvterm.cvterm_id,
            object_id=object_cvterm.cvterm_id)
        cvrel.save()

    def handle(self, *args, **options):
        """Execute the main function."""
        # Load the ontology file
        with open(options['go']) as obo_file:
            G = read_obo(obo_file)

        cv_definition = G.graph['date']

        if options.get('verbosity') > 0:
            self.stdout.write('Preprocessing')

        ontologies = [
                'biological_process',
                'molecular_function',
                'cellular_component',
                'external']

        # Check if the ontologies are already loaded
        for ontology in ontologies:

            try:
                cv = Cv.objects.get(name=ontology)
                if cv is not None:
                    if options.get('verbosity') > 0:
                        raise IntegrityError(
                                self.style.ERROR(
                                    'cv: cannot load {} {} '
                                    '(already registered)'.format(
                                        ontology, cv_definition)))
            except ObjectDoesNotExist:

                # Save ontology to the Cv model
                cv = Cv.objects.create(name=ontology,
                                       definition=cv_definition)
                cv.save()

        # Creating db internal to be used for creating dbxref objects
        db_internal, created = Db.objects.get_or_create(name='internal')
        # Creating cvterm is_anti_symmetric to be used as type_id in cvtermprop
        dbxref_exact, created = Dbxref.objects.get_or_create(
            db=db_internal, accession='exact')

        cv_synonym_type, created = Cv.objects.get_or_create(
            name='synonym_type')
        Cvterm.objects.get_or_create(cv=cv_synonym_type,
                                     name='exact',
                                     definition='',
                                     dbxref=dbxref_exact,
                                     is_obsolete=0,
                                     is_relationshiptype=0)

        # Load typedefs as Dbxrefs and Cvterm
        if options.get('verbosity') > 0:
            self.stdout.write(
                'Loading typedefs ({} threads)'.format(options.get('cpu')))

        pool = ThreadPoolExecutor(max_workers=options.get('cpu'))
        tasks = list()
        for typedef in G.graph['typedefs']:
            tasks.append(pool.submit(self.store_type_def, typedef))
        for task in tqdm(as_completed(tasks), total=len(tasks)):
            if task.result():
                raise(task.result())

        # Load the cvterms
        if options.get('verbosity') > 0:
            self.stdout.write(
                'Loading terms ({} threads)'.format(options.get('cpu')))

        # Creating cvterm comment to be used as type_id in cvtermprop
        dbxref_comment, created = Dbxref.objects.get_or_create(
            db=db_internal, accession='comment')

        cv_cvterm_property_type, created = Cv.objects.get_or_create(
            name='cvterm_property_type')
        Cvterm.objects.get_or_create(cv=cv_cvterm_property_type,
                                     name='comment',
                                     definition='',
                                     dbxref=dbxref_comment,
                                     is_obsolete=0,
                                     is_relationshiptype=0)

        lock = Lock()
        tasks = list()
        for n, data in G.nodes(data=True):
            tasks.append(pool.submit(self.store_term, n, data, lock))
        for task in tqdm(as_completed(tasks), total=len(tasks)):
            if task.result():
                raise(task.result())

        # Load the relationship between cvterms
        if options.get('verbosity') > 0:
            self.stdout.write(
                'Loading relationships ({} threads)'.format(
                    options.get('cpu')))

        # creating term is_a to be used as type_id in cvterm_relationship
        db_obo_rel, created = Db.objects.get_or_create(name='obo_rel')
        dbxref_is_a, created = Dbxref.objects.get_or_create(
            db=db_obo_rel, accession='is_a')

        cv_relationship, created = Cv.objects.get_or_create(
            name='relationship')
        Cvterm.objects.get_or_create(cv=cv_relationship,
                                     name='is_a',
                                     definition='',
                                     dbxref=dbxref_is_a,
                                     is_obsolete=0,
                                     is_relationshiptype=1)

        tasks = list()
        for u, v, type in G.edges(keys=True):
            tasks.append(pool.submit(
                self.store_relationship, u, v, type))
        for task in tqdm(as_completed(tasks), total=len(tasks)):
            if task.result():
                raise(task.result())

        # DONE
        if options.get('verbosity') > 0:
            self.stdout.write(self.style.SUCCESS('Done'))

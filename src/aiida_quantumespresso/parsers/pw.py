# -*- coding: utf-8 -*-
"""`Parser` implementation for the `PwCalculation` calculation job class."""
import traceback

from aiida import orm
from aiida.common import exceptions
from aiida.engine import ExitCode
import numpy

from aiida_quantumespresso.calculations.pw import PwCalculation
from aiida_quantumespresso.utils.mapping import get_logging_container
from aiida_quantumespresso.workflows.protocols.utils import recursive_merge

from .base import BaseParser
from .parse_raw.pw import reduce_symmetries


def fix_sirius_xml_prints(array):
    """Fix an issue where SIRIUS prints very small numbers incorrectly.
    
    In some cases SIRIUS prints very small numbers in scientific notation, but
    without the capital `E` to indicate the exponent:

        
        <forces rank="2" dims="           3           6">
        3.220681500679849E-86   4.347898683069749-103  -3.696810758148386E-49

    This function will fix this by converting any number that cannot be converted into
    a float to zero.
    """
    def try_convert(s):
        try:
            return float(s)
        except (ValueError, TypeError):
            return 0
        
    return numpy.vectorize(try_convert)(array)


class PwParser(BaseParser):
    """`Parser` implementation for the `PwCalculation` calculation job class."""

    def parse(self, **kwargs):
        """Parse the retrieved files of a completed `PwCalculation` into output nodes.

        Two nodes that are expected are the default 'retrieved' `FolderData` node which will store the retrieved files
        permanently in the repository. The second required node is a filepath under the key `retrieved_temporary_files`
        which should contain the temporary retrieved files.
        """
        # pylint: disable=too-many-statements
        dir_with_bands = None
        crash_file = None
        self.exit_code_xml = None
        self.exit_code_stdout = None
        self.exit_code_parser = None

        try:
            settings = self.node.inputs.settings.get_dict()
        except exceptions.NotExistent:
            settings = {}

        # Look for optional settings input node and potential 'parser_options' dictionary within it
        parser_options = settings.get(self.get_parser_settings_key(), None)

        # Verify that the retrieved_temporary_folder is within the arguments if temporary files were specified
        # if self.node.base.attributes.get('retrieve_temporary_list', None):
        #     try:
        #         dir_with_bands = kwargs['retrieved_temporary_folder']
        #     except KeyError:
        #         return self.exit(self.exit_codes.ERROR_NO_RETRIEVED_TEMPORARY_FOLDER)

        # We check if the `CRASH` file was retrieved. If so, we parse its output
        crash_file_filename = self.node.process_class._CRASH_FILE
        if crash_file_filename in self.retrieved.base.repository.list_object_names():
            crash_file = self.retrieved.base.repository.get_object_content(crash_file_filename)

        parameters = self.node.inputs.parameters.get_dict()
        parsed_xml, logs_xml = self.parse_xml(dir_with_bands, parser_options)
        parsed_stdout, logs_stdout = self.parse_stdout(parameters, parser_options, crash_file)

        if not parsed_xml and self.node.get_option('without_xml'):
            parsed_xml = parsed_stdout

        parsed_bands = parsed_xml.pop('bands', {})
        parsed_structure = parsed_xml.pop('structure', {})
        parsed_trajectory = parsed_xml.pop('trajectory', {})
        self.backwards_compatibility_trajectory(parsed_trajectory, parsed_stdout)

        parsed_parameters = self.build_output_parameters(parsed_stdout, parsed_xml)
        self.backwards_compatibility_parameters(parsed_parameters, parsed_stdout)

        # Append the last frame of some of the smaller trajectory arrays to the parameters for easy querying
        self.final_trajectory_frame_to_parameters(parsed_parameters, parsed_trajectory)

        # If the parser option 'all_symmetries' is False, we reduce the raw parsed symmetries to save space
        all_symmetries = False if parser_options is None else parser_options.get('all_symmetries', False)
        if not all_symmetries and 'cell' in parsed_structure:
            reduce_symmetries(parsed_parameters, parsed_structure, self.logger)

        structure = self.build_output_structure(parsed_structure)
        kpoints = self.build_output_kpoints(parsed_parameters, structure)
        bands = self.build_output_bands(parsed_bands, kpoints)
        trajectory = self.build_output_trajectory(parsed_trajectory, structure)

        # Determine whether the input kpoints were defined as a mesh or as an explicit list
        try:
            self.node.inputs.kpoints.get_kpoints()
        except AttributeError:
            input_kpoints_explicit = False
        else:
            input_kpoints_explicit = True

        # Only attach the `KpointsData` as output if there will be no `BandsData` output and inputs were defined as mesh
        if kpoints and not bands and not input_kpoints_explicit:
            self.out('output_kpoints', kpoints)

        if bands:
            self.out('output_band', bands)

        if trajectory:
            self.out('output_trajectory', trajectory)

        if not structure.is_stored:
            self.out('output_structure', structure)

        # Separate the atomic_occupations dictionary in its own node if it is present
        atomic_occupations = parsed_parameters.pop('atomic_occupations', None)
        if atomic_occupations:
            self.out('output_atomic_occupations', orm.Dict(atomic_occupations))

        self.out('output_parameters', orm.Dict(parsed_parameters))

        # Emit the logs returned by the XML and stdout parsing through the logger
        # If the calculation was an initialization run, reset the XML logs because they will contain a lot of verbose
        # warnings from the schema parser about incomplete data, but that is to be expected in an initialization run.
        if settings.get('ONLY_INITIALIZATION', False):
            logs_xml.pop('error')

        ignore = ['Error while parsing ethr.', 'DEPRECATED: symmetry with ibrav=0, use correct ibrav instead']
        self.emit_logs([logs_stdout, logs_xml], ignore=ignore)

        # If either the stdout or XML were incomplete or corrupt investigate the potential cause
        if self.exit_code_stdout or self.exit_code_xml:

            # First check whether the scheduler already reported an exit code.
            if self.node.exit_status is not None:

                # The following scheduler errors should correspond to cases where we can simply restart the calculation
                # and have a chance that the calculation will succeed as the error can be transient.
                recoverable_scheduler_error = self.node.exit_status in [
                    PwCalculation.exit_codes.ERROR_SCHEDULER_OUT_OF_WALLTIME.status,
                    PwCalculation.exit_codes.ERROR_SCHEDULER_NODE_FAILURE.status,
                ]

                if self.get_calculation_type() in ['relax', 'vc-relax'] and recoverable_scheduler_error:
                    return PwCalculation.exit_codes.ERROR_IONIC_INTERRUPTED_PARTIAL_TRAJECTORY

                # Now it is unlikely we can provide a more specific exit code so we keep the scheduler one.
                return ExitCode(self.node.exit_status, self.node.exit_message)

        # Check for specific known problems that can cause a pre-mature termination of the calculation
        exit_code = self.validate_premature_exit(logs_stdout)
        if exit_code:
            return self.exit(exit_code)

        # If the both stdout and xml exit codes are set, there was a basic problem with both output files and there
        # is no need to investigate any further.
        if self.exit_code_stdout and self.exit_code_xml:
            return self.exit(self.exit_codes.ERROR_OUTPUT_FILES)

        if self.exit_code_stdout:
            return self.exit(self.exit_code_stdout)

        if self.exit_code_xml:
            return self.exit(self.exit_code_xml)

        # First determine issues that can occurr for all calculation types. Note that the generic errors, that are
        # common to all types are done first. If a problem is found there, we return the exit code and don't continue
        for validator in [self.validate_electronic, self.validate_dynamics, self.validate_ionic]:
            exit_code = validator(trajectory, parsed_parameters, logs_stdout)
            if exit_code:
                return self.exit(exit_code)

    def backwards_compatibility_trajectory(self, parsed_trajectory, parsed_stdout):
        """."""
        # For QE v7.0 and lower, the stress is not reported in the trajectory steps in the XML. The XML parsing will
        # therefore only add the stress of the last SCF to the trajectory. We need to replace this with the trajectory
        # parsed from the SCF to have the data of all frames.
        if 'trajectory' not in parsed_stdout:
            return

        if self.get_calculation_type() in [
            'relax', 'vc-relax'
        ] and ('stress' not in parsed_trajectory or
               len(parsed_trajectory['stress']) == 1) and 'stress' in parsed_stdout['trajectory']:
            parsed_trajectory['stress'] = parsed_stdout['trajectory']['stress']

        for key in [
            'energy_accuracy', 'energy_one_electron', 'energy_threshold', 'energy_smearing', 'energy_one_center_paw',
            'energy_vdw', 'fermi_energy', 'scf_accuracy', 'steps', 'total_force', 'stress', 'total_magnetization',
            'absolute_magnetization', 'atomic_magnetic_moments', 'atomic_charges'
        ]:
            if key not in parsed_trajectory and key in parsed_stdout['trajectory']:
                parsed_trajectory[key] = parsed_stdout['trajectory'][key]

    @staticmethod
    def backwards_compatibility_parameters(parsed_parameters, parsed_stdout):
        """."""
        keys = [
            'energy_smearing_units',
            'energy_one_center_paw_units',
            'init_wall_time_seconds',
            'stress_units',
            'wall_time',
            'wall_time_seconds',
            'number_ionic_steps',
            'estimated_ram_per_process',
            'estimated_ram_per_process_units',
            'estimated_ram_total',
            'estimated_ram_total_units',
            'forces_units',
            'total_force_units',
            'forces_units',
            'number_of_bands',
            'number_of_k_points',
        ]

        for key in keys:
            if key not in parsed_parameters and key in parsed_stdout:
                parsed_parameters[key] = parsed_stdout[key]

    def get_calculation_type(self):
        """Return the type of the calculation."""
        return self.node.inputs.parameters.base.attributes.get('CONTROL', {}).get('calculation', 'scf')

    def validate_premature_exit(self, logs):
        """Analyze problems that will cause a pre-mature termination of the calculation, controlled or not."""
        if 'ERROR_OUT_OF_WALLTIME' in logs['error'] and 'ERROR_OUTPUT_STDOUT_INCOMPLETE' in logs['error']:
            return self.exit_codes.ERROR_OUT_OF_WALLTIME_INTERRUPTED

        for error_label in [
            'ERROR_OUT_OF_WALLTIME',
            'ERROR_CHARGE_IS_WRONG',
            'ERROR_SYMMETRY_NON_ORTHOGONAL_OPERATION',
            'ERROR_DEXX_IS_NEGATIVE',
            'ERROR_COMPUTING_CHOLESKY',
            'ERROR_NPOOLS_TOO_HIGH',
            'ERROR_DIAGONALIZATION_TOO_MANY_BANDS_NOT_CONVERGED',
            'ERROR_S_MATRIX_NOT_POSITIVE_DEFINITE',
            'ERROR_ZHEGVD_FAILED',
            'ERROR_QR_FAILED',
            'ERROR_G_PAR',
            'ERROR_EIGENVECTOR_CONVERGENCE',
            'ERROR_BROYDEN_FACTORIZATION',
            'ERROR_RADIAL_FFT_SIGNIFICANT_VOLUME_CONTRACTION',
        ]:
            if error_label in logs['error']:
                return self.exit_codes.get(error_label)

    def validate_electronic(self, trajectory, parameters, logs):
        """Analyze problems that are specific to `electronic` type calculations: i.e. `scf`, `nscf` and `bands`."""
        if self.get_calculation_type() not in ['scf', 'nscf', 'bands']:
            return

        if 'ERROR_ELECTRONIC_CONVERGENCE_NOT_REACHED' in logs['error']:
            scf_must_converge = self.node.inputs.parameters.base.attributes.get('ELECTRONS',
                                                                                {}).get('scf_must_converge', True)
            electron_maxstep = self.node.inputs.parameters.base.attributes.get('ELECTRONS',
                                                                               {}).get('electron_maxstep', 1)

            if electron_maxstep == 0 or not scf_must_converge:
                return self.exit_codes.WARNING_ELECTRONIC_CONVERGENCE_NOT_REACHED
            else:
                return self.exit_codes.ERROR_ELECTRONIC_CONVERGENCE_NOT_REACHED

    def validate_dynamics(self, trajectory, parameters, logs):
        """Analyze problems that are specific to `dynamics` type calculations: i.e. `md` and `vc-md`."""
        if self.get_calculation_type() not in ['md', 'vc-md']:
            return

    def validate_ionic(self, trajectory, parameters, logs):
        """Analyze problems that are specific to `ionic` type calculations: i.e. `relax` and `vc-relax`."""
        if self.get_calculation_type() not in ['relax', 'vc-relax']:
            return

        electronic_convergence_reached = 'ERROR_ELECTRONIC_CONVERGENCE_NOT_REACHED' not in logs.error
        ionic_convergence_reached = 'ERROR_IONIC_CONVERGENCE_NOT_REACHED' not in logs.error
        bfgs_history_failure = 'ERROR_IONIC_CYCLE_BFGS_HISTORY_FAILURE' in logs.error
        maximum_ionic_steps_reached = 'ERROR_MAXIMUM_IONIC_STEPS_REACHED' in logs.warning
        final_scf = parameters.get('final_scf', False)

        # The electronic self-consistency cycle failed before reaching ionic convergence
        if not ionic_convergence_reached and not electronic_convergence_reached:
            return self.exit_codes.ERROR_IONIC_CYCLE_ELECTRONIC_CONVERGENCE_NOT_REACHED

        # Ionic convergence was not reached because maximum number of steps was exceeded
        if not ionic_convergence_reached and maximum_ionic_steps_reached:
            return self.exit_codes.ERROR_IONIC_CYCLE_EXCEEDED_NSTEP

        # BFGS fails twice in a row in which case QE will print that convergence is reached while it is not necessarily
        if bfgs_history_failure:

            # If electronic convergence was not reached, this had to have been a `vc-relax` where final SCF failed
            if not electronic_convergence_reached:
                return self.exit_codes.ERROR_IONIC_CYCLE_BFGS_HISTORY_AND_FINAL_SCF_FAILURE

            # If the forces and optionally stresses are already converged, consider the calculation successful
            if self.is_ionically_converged(trajectory):
                return

            return self.exit_codes.ERROR_IONIC_CYCLE_BFGS_HISTORY_FAILURE

        # Electronic convergence could not have been reached either during ionic relaxation or during final scf
        if not electronic_convergence_reached:
            if final_scf:
                return self.exit_codes.ERROR_IONIC_CONVERGENCE_REACHED_FINAL_SCF_FAILED

            return self.exit_codes.ERROR_IONIC_CYCLE_ELECTRONIC_CONVERGENCE_NOT_REACHED

        # Here we have no direct warnings from Quantum ESPRESSO that suggest something went wrong, but we better make
        # sure and double check manually that all forces (and optionally stresses) are converged.
        if not self.is_ionically_converged(trajectory):

            if self.is_ionically_converged(trajectory, except_final_scf=True):
                # The forces and stresses of ionic cycle are below threshold, but those of the final SCF exceed them.
                # This is not necessarily a problem since the calculation starts from scratch after the variable cell
                # relaxation and the forces and stresses can be slightly different. Still it is useful to distinguish
                # these calculations so we return a special exit code.
                return self.exit_codes.ERROR_IONIC_CONVERGENCE_REACHED_EXCEPT_IN_FINAL_SCF

            return self.exit_codes.ERROR_IONIC_CONVERGENCE_NOT_REACHED

    def is_ionically_converged(self, trajectory, except_final_scf=False):
        """Verify that the calculation was ionically converged.

        For a `relax` calculation this means the forces stored in the `trajectory` are all below the force convergence
        threshold which is retrieved from the input parameters. For a `vc-relax` calculation, the stress should also
        give a pressure that is below the pressure convergence threshold.

        :param trajectory: the output trajectory data
        :param except_final_scf: if True will return whether the calculation is converged except for the final scf.
        """
        from aiida_quantumespresso.calculations import _uppercase_dict
        from aiida_quantumespresso.utils.defaults.calculation import pw
        from aiida_quantumespresso.utils.validation.trajectory import verify_convergence_trajectory

        relax_type = self.get_calculation_type()
        parameters = self.node.inputs.parameters.get_dict()
        threshold_forces = parameters.get('CONTROL', {}).get('forc_conv_thr', pw.forc_conv_thr)
        threshold_stress = parameters.get('CELL', {}).get('press_conv_thr', pw.press_conv_thr)
        external_pressure = parameters.get('CELL', {}).get('press', 0)

        if 'settings' in self.node.inputs:
            settings = _uppercase_dict(self.node.inputs.settings.get_dict(), dict_name='settings')
        else:
            settings = {}

        fixed_coords = settings.get('FIXED_COORDS', None)

        # Through the `cell_dofree` the degrees of freedom of the cell can be constrained, which makes the threshold on
        # the stress hard to interpret. Therefore, unless the `cell_dofree` is set to the default `all` where the cell
        # is fully unconstrained, the stress is ignored even if an explicit `press_conv_thr` is specified in the inputs.
        constrained_cell = parameters.get('CELL', {}).get('cell_dofree', 'all') != 'all'

        if constrained_cell:
            threshold_stress = None

        if relax_type == 'relax':
            return verify_convergence_trajectory(
                trajectory=trajectory, index=-1, threshold_forces=threshold_forces, fixed_coords=fixed_coords
            )

        if relax_type == 'vc-relax':
            values = [threshold_forces, threshold_stress, external_pressure, fixed_coords]
            converged_relax = verify_convergence_trajectory(trajectory, -2, *values)
            converged_final = verify_convergence_trajectory(trajectory, -1, *values)

            return converged_relax and (converged_final or except_final_scf)

        raise RuntimeError(f'unknown relax_type: {relax_type}')

    def parse_xml(self, dir_with_bands=None, parser_options=None):
        """Parse the XML output file.

        :param dir_with_bands: absolute path to directory containing individual k-point XML files for old XML format.
        :param parser_options: optional dictionary with parser options
        :return: tuple of two dictionaries, first with raw parsed data and second with log messages
        """
        from .parse_xml.exceptions import XMLParseError, XMLUnsupportedFormatError
        from .parse_xml.pw.parse import parse_xml

        logs = get_logging_container()
        parsed_data = {}

        object_names = self.retrieved.base.repository.list_object_names()
        xml_files = [xml_file for xml_file in self.node.process_class.xml_filenames if xml_file in object_names]

        if not xml_files:
            if not self.node.get_option('without_xml'):
                self.exit_code_xml = self.exit_codes.ERROR_OUTPUT_XML_MISSING
            return parsed_data, logs

        if len(xml_files) > 1:
            self.exit_code_xml = self.exit_codes.ERROR_OUTPUT_XML_MULTIPLE
            return parsed_data, logs

        try:
            with self.retrieved.base.repository.open(xml_files[0]) as xml_file:
                parsed_data, logs = parse_xml(xml_file, dir_with_bands)
        except IOError:
            self.exit_code_xml = self.exit_codes.ERROR_OUTPUT_XML_READ
        except XMLParseError:
            self.exit_code_xml = self.exit_codes.ERROR_OUTPUT_XML_PARSE
        except XMLUnsupportedFormatError:
            self.exit_code_xml = self.exit_codes.ERROR_OUTPUT_XML_FORMAT
        except Exception as exc:
            logs.critical.append(traceback.format_exc())
            self.exit_code_xml = self.exit_codes.ERROR_UNEXPECTED_PARSER_EXCEPTION.format(exception=exc)

        return parsed_data, logs

    def parse_stdout(self, parameters, parser_options=None, crash_file=None):
        """Parse the stdout output file.

        :param parameters: the input parameters dictionary
        :param parser_options: optional dictionary with parser options
        :return: tuple of two dictionaries, first with raw parsed data and second with log messages
        """
        from aiida_quantumespresso.parsers.parse_raw.pw import parse_stdout
        from aiida_quantumespresso.parsers.parse_raw.pw import parse_sirius_stdout

        logs = get_logging_container()
        parsed_data = {}

        filename_stdout = self.node.base.attributes.get('output_filename')

        if filename_stdout not in self.retrieved.base.repository.list_object_names():
            self.exit_code_stdout = self.exit_codes.ERROR_OUTPUT_STDOUT_MISSING
            return parsed_data, logs

        try:
            stdout = self.retrieved.base.repository.get_object_content(filename_stdout)
        except IOError:
            self.exit_code_stdout = self.exit_codes.ERROR_OUTPUT_STDOUT_READ
            return parsed_data, logs

        try:
            parsed_data, logs = parse_stdout(stdout, parameters, parser_options, crash_file=crash_file)
        except Exception as exc:
            logs.critical.append(traceback.format_exc())
            self.exit_code_stdout = self.exit_codes.ERROR_UNEXPECTED_PARSER_EXCEPTION.format(exception=exc)

        parsed_data = recursive_merge(parsed_data, parse_sirius_stdout(stdout))

        # If the stdout was incomplete, most likely the job was interrupted before it could cleanly finish, so the
        # output files are most likely corrupt and cannot be restarted from
        if 'ERROR_OUTPUT_STDOUT_INCOMPLETE' in logs['error']:
            self.exit_code_stdout = self.exit_codes.ERROR_OUTPUT_STDOUT_INCOMPLETE

        # Under certain conditions, such as the XML missing or being incorrect, the structure data might be incomplete.
        # Since following code depends on it, we replace missing information taken from the input structure.
        structure = self.node.inputs.structure
        parsed_data.setdefault('structure', {}).setdefault('cell', {})

        if 'lattice_vectors' not in parsed_data['structure']['cell']:
            parsed_data['structure']['cell']['lattice_vectors'] = structure.cell

        if 'atoms' not in parsed_data['structure']['cell']:
            symbols = {s.kind_name: structure.get_kind(s.kind_name).symbol for s in structure.sites}
            parsed_data['structure']['cell']['atoms'] = [(symbols[s.kind_name], s.position) for s in structure.sites]

        return parsed_data, logs

    @staticmethod
    def build_output_parameters(parsed_stdout, parsed_xml):
        """Build the dictionary of output parameters from the raw parsed data.

        The output parameters are based on the union of raw parsed data from the XML and stdout output files.
        Currently, if both raw parsed data dictionaries contain the same key, the stdout version takes precedence, but
        this should not occur as the `parse_stdout` method should already have solved these conflicts.

        :param parsed_stdout: the raw parsed data dictionary from the stdout output file
        :param parsed_xml: the raw parsed data dictionary from the XML output file
        :return: the union of the two raw parsed data dictionaries
        """
        return parsed_xml

    def build_output_structure(self, parsed_structure):
        """Build the output structure from the raw parsed data.

        :param parsed_structure: the dictionary with raw parsed structure data
        :return: a new `StructureData` created from the parsed data iff the calculation type produces a new structure
            and the parsed data contained a cell definition. In all other cases, the input structure will be returned.
        """
        from aiida_quantumespresso.parsers.parse_raw import convert_qe_to_aiida_structure

        type_calc = self.node.inputs.parameters.get_dict()['CONTROL']['calculation']

        if type_calc not in ['relax', 'vc-relax', 'md', 'vc-md'] or 'cell' not in list(parsed_structure.keys()):
            return self.node.inputs.structure

        return convert_qe_to_aiida_structure(parsed_structure, self.node.inputs.structure)

    @staticmethod
    def build_output_trajectory(parsed_trajectory, structure):
        """Build the output trajectory from the raw parsed trajectory data.

        :param parsed_trajectory: the raw parsed trajectory data
        :return: a `TrajectoryData` or None
        """
        fractional = False

        if 'atomic_positions_relax' in parsed_trajectory:
            positions = numpy.array(parsed_trajectory.pop('atomic_positions_relax'))
        elif 'atomic_fractionals_relax' in parsed_trajectory:
            fractional = True
            positions = numpy.array(parsed_trajectory.pop('atomic_fractionals_relax'))
        else:
            # The positions were never printed, the calculation did not change the structure
            positions = numpy.array([[site.position for site in structure.sites]])

        try:
            cells = numpy.array(parsed_trajectory.pop('lattice_vectors_relax'))
        except KeyError:
            # The cell is never printed, the calculation was at fixed cell
            cells = numpy.array([structure.cell])

        # Ensure there are as many frames for cell as positions, even when the calculation was done at fixed cell
        if len(cells) == 1 and len(positions) > 1:
            cells = numpy.array([cells[0]] * len(positions))

        if fractional:
            # convert positions to cartesian
            positions = numpy.einsum('ijk, ikm -> ijm', positions, cells)

        symbols = [str(site.kind_name) for site in structure.sites]
        stepids = numpy.arange(len(positions))

        trajectory = orm.TrajectoryData()
        trajectory.set_trajectory(
            stepids=stepids,
            cells=cells,
            symbols=symbols,
            positions=positions,
        )

        for key, value in parsed_trajectory.items():
            if key in (
                'forces',
                'stress'
            ):
                trajectory.set_array(key, fix_sirius_xml_prints(numpy.array(value)))
            else:
                trajectory.set_array(key, numpy.array(value))

        return trajectory

    def build_output_kpoints(self, parsed_parameters, structure):
        """Build the output kpoints from the raw parsed data.

        :param parsed_parameters: the raw parsed data
        :return: a `KpointsData` or None
        """
        k_points_list = parsed_parameters.pop('k_points', None)
        k_points_units = parsed_parameters.pop('k_points_units', None)
        k_points_weights_list = parsed_parameters.pop('k_points_weights', None)

        if k_points_list is None or k_points_weights_list is None:
            return None

        if k_points_units != '1 / angstrom':
            self.logger.error('Error in kpoints units (should be cartesian)')
            self.exit_code_parser = self.exit_codes.ERROR_INVALID_KPOINT_UNITS
            return None

        kpoints = orm.KpointsData()
        kpoints.set_cell_from_structure(structure)
        kpoints.set_kpoints(k_points_list, cartesian=True, weights=k_points_weights_list)

        return kpoints

    def build_output_bands(self, parsed_bands, parsed_kpoints=None):
        """Build the output bands from the raw parsed bands data.

        :param parsed_bands: the raw parsed bands data
        :param parsed_kpoints: the `KpointsData` to use for the bands
        :return: a `BandsData` or None
        """
        if not parsed_bands or not parsed_kpoints:
            return

        # In the case of input kpoints that define a list of k-points, i.e. along high-symmetry path, and explicit
        # labels, set those labels also on the output kpoints to be used for the bands. This will allow plotting
        # utilities to place k-point labels along the x-axis.
        try:
            self.node.inputs.kpoints.get_kpoints()
            parsed_kpoints.labels = self.node.inputs.kpoints.labels
        except (AttributeError, ValueError, TypeError):
            # AttributeError: input kpoints defines a mesh, not an explicit list
            # TypeError: inputs kpoints do not define any labels
            # ValueError: input kpoints labels are not commensurate with `parsed_kpoints`
            pass

        # Correct the occupation for nspin=1 calculations where Quantum ESPRESSO populates each band only halfway
        if len(parsed_bands['occupations']) > 1:
            occupations = numpy.array(parsed_bands['occupations'])
        else:
            occupations = numpy.array(parsed_bands['occupations'][0])

        occupations = fix_sirius_xml_prints(occupations)

        if len(parsed_bands['occupations']) > 1:
            occupations *= 2.

        bands_energies = parsed_bands['bands'][0] if len(parsed_bands['bands']) == 1 else parsed_bands['bands']

        bands = orm.BandsData()
        bands.set_kpointsdata(parsed_kpoints)
        bands.set_bands(bands_energies, units=parsed_bands['bands_units'], occupations=occupations)

        return bands

    @staticmethod
    def get_parser_settings_key():
        """Return the key that contains the optional parser options in the `settings` input node."""
        return 'parser_options'

    @staticmethod
    def final_trajectory_frame_to_parameters(parameters, parsed_trajectory):
        """Copy the last frame of certain properties from the `TrajectoryData` to the outputs parameters.

        This makes these properties queryable.
        """
        include_keys = [
            'energy',
            'energy_accuracy',
            'energy_ewald',
            'energy_hartree',
            'energy_hubbard',
            'energy_one_electron',
            'energy_threshold',
            'energy_vdw',
            'energy_xc',
            'energy_smearing',
            'energy_one_center_paw',
            'energy_est_exchange',
            'energy_fock',
            'scf_iterations',
            'fermi_energy',
            'total_force',
            'total_magnetization',
            'absolute_magnetization',
        ]

        for property_key, property_values in parsed_trajectory.items():

            if property_key not in include_keys or not property_values:
                continue

            parameters[property_key] = property_values[-1]

    def get_extended_symmetries(self):
        """Return the extended dictionary of symmetries based on reduced symmetries stored in output parameters."""
        from aiida_quantumespresso.parsers.parse_raw.pw import get_symmetry_mapping

        possible_symmetries = get_symmetry_mapping()
        parameters = self.node.base.links.get_outgoing(node_class=orm.Dict).get_node_by_label('output_parameters')

        symmetries_extended = []
        symmetries_reduced = parameters.get_dict()['symmetries']  # rimetti lo zero

        for element in symmetries_reduced:

            symmetry = {}

            for keys in ['t_rev', 'equivalent_ions', 'fractional_translation']:
                try:
                    symmetry[keys] = element[keys]
                except KeyError:
                    pass

            # expand the rest
            symmetry['name'] = possible_symmetries[element['symmetry_number']]['name']
            symmetry['rotation'] = possible_symmetries[element['symmetry_number']]['matrix']
            symmetry['inversion'] = possible_symmetries[element['symmetry_number']]['inversion']

            symmetries_extended.append(symmetry)

        return symmetries_extended

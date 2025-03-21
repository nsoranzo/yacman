import os

import pytest
from jsonschema.exceptions import ValidationError

import yacman
from yacman.const import FILEPATH_KEY, IK, RO_KEY


class TestWriting:
    def test_basic_write(self, cfg_file, list_locks, data_path, locked_cfg_file):
        yacmap = yacman.YacAttMap(filepath=cfg_file, writable=True)
        assert os.path.exists(locked_cfg_file)
        yacmap.write()

    def test_write_creates_file(self, data_path, list_locks):
        with pytest.warns(UserWarning):
            yacmap = yacman.YacAttMap(entries={}, writable=True)
        yacmap.write(filepath=make_cfg_file_path("writeout.yaml", data_path))
        assert os.path.exists(make_lock_path("writeout.yaml", data_path))
        assert os.path.exists(make_cfg_file_path("writeout.yaml", data_path))
        os.remove(make_cfg_file_path("writeout.yaml", data_path))

    @pytest.mark.parametrize(
        ["name", "entry"], [("updated.yaml", "update"), ("updated1.yaml", "update1")]
    )
    def test_entries_update(self, name, data_path, entry):
        filepath = make_cfg_file_path(name, data_path)
        yacmap = yacman.YacAttMap(entries={})
        yacmap.test = entry
        yacmap.write(filepath=filepath)
        yacmap.make_readonly()  # need to remove the lock; the next line locks for read
        yacmapin = yacman.YacAttMap(filepath=filepath, writable=False)
        assert yacmapin.test == entry
        os.remove(filepath)

    @pytest.mark.parametrize("name", ["test.yaml", "test1.yaml"])
    def test_warn_on_write_when_not_locked(
        self, name, data_path, cfg_file, locked_cfg_file
    ):
        yacmap = yacman.YacAttMap(filepath=cfg_file, writable=True)
        filename = make_cfg_file_path(name, data_path)
        f = os.open(filename, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(f)
        with pytest.warns(UserWarning):
            yacmap.write(filename)
        os.remove(filename)
        assert os.path.exists(make_lock_path(name, data_path))
        assert not os.path.exists(locked_cfg_file)


class TestExceptions:
    def test_cant_write_ro_mode(self, cfg_file, list_locks):
        yacmap = yacman.YacAttMap(filepath=cfg_file, writable=False)
        with pytest.raises(OSError):
            yacmap.write(cfg_file)

    def test_filename_required_when_object_created_from_mapping(self):
        yacmap = yacman.YacAttMap(entries={})
        with pytest.raises(TypeError):
            yacmap.write()

    def test_unlock_errors_when_no_filepath_provided(self, cfg_file):
        yacmap = yacman.YacAttMap({})
        with pytest.raises(TypeError):
            yacmap.make_readonly()

    def test_warnings(self, cfg_file):
        with pytest.warns(None):
            yacman.YacAttMap({}, writable=True)


class TestManipulationMethods:
    def test_make_readonly_removes_lock_and_returns_true(self, cfg_file, list_locks):
        yacmap = yacman.YacAttMap(filepath=cfg_file, writable=True)
        assert yacmap.make_readonly()
        assert len(list_locks) == 0

    def test_make_readonly_returns_false_if_nothing_unlocked(self, cfg_file):
        yacmap = yacman.YacAttMap(filepath=cfg_file, writable=False)
        assert not yacmap.make_readonly()

    def test_make_writable_doesnt_change_already_writable_objects(self, cfg_file):
        yacmap = yacman.YacAttMap(filepath=cfg_file, writable=True)
        assert yacmap == yacmap.make_writable()

    def test_make_writable_makes_object_writable(self, cfg_file):
        yacmap = yacman.YacAttMap(filepath=cfg_file, writable=False)
        yacmap.make_writable()
        assert not getattr(yacmap[IK], RO_KEY, True)

    @pytest.mark.parametrize("name", ["test.yaml", "test1.yaml"])
    def test_make_writable_changes_filepath(self, cfg_file, name, data_path):
        yacmap = yacman.YacAttMap(filepath=cfg_file, writable=False)
        yacmap.make_writable(make_cfg_file_path(name, data_path))
        assert getattr(yacmap[IK], FILEPATH_KEY) != cfg_file

    @pytest.mark.parametrize("name", ["test.yaml", "test1.yaml"])
    def test_make_writable_sets_filepath(self, name, data_path):
        yacmap = yacman.YacAttMap(entries={})
        yacmap.make_writable(make_cfg_file_path(name, data_path))
        assert os.path.exists(make_lock_path(name, data_path))
        assert getattr(yacmap[IK], FILEPATH_KEY) is not None

    @pytest.mark.parametrize("name", ["test.yaml", "test1.yaml"])
    def test_make_writable_creates_locks(self, cfg_file, name, data_path):
        yacmap = yacman.YacAttMap(filepath=cfg_file, writable=False)
        yacmap.make_writable(make_cfg_file_path(name, data_path))
        assert os.path.exists(make_lock_path(name, data_path))

    def test_make_writable_rereads_source_file(self, cfg_file):
        """
        Test that the the changes made to the cfg by other processes
        are re-read after the original process is made writable
        """
        yacmap1 = yacman.YacAttMap(filepath=cfg_file, writable=False)
        yacmap = yacman.YacAttMap(filepath=cfg_file, writable=True)
        yacmap.test = "test"
        yacmap.write()
        yacmap.make_readonly()
        yacmap1.make_writable(cfg_file)
        assert yacmap1.test == "test"
        # remove added entry after the test
        if "test" in yacmap1:
            del yacmap1["test"]
            yacmap1.write()
        yacmap1.make_readonly()

    @pytest.mark.parametrize("name", ["test.yaml", "test1.yaml"])
    def test_make_writable_removes_previous_locks(self, cfg_file, name, data_path):
        yacmap = yacman.YacAttMap(filepath=cfg_file, writable=True)
        yacmap.make_writable(make_cfg_file_path(name, data_path))
        assert not os.path.exists(make_lock_path(cfg_file, data_path))
        yacmap.make_readonly()


class TestReading:
    def test_locks_before_reading_by_default(self, data_path, cfg_file):
        """
        Here we test that the object constructor waits for a second and
        raises a Runtime error because it tries to lock the file for reading by default
        """
        yacmap = yacman.YacAttMap(filepath=cfg_file, writable=True)
        with pytest.raises(RuntimeError):
            yacman.YacAttMap(filepath=cfg_file, wait_max=1)
        yacmap.make_readonly()

    def test_skip_locks_before_reading(self, data_path, cfg_file):
        """
        Here we test that the object constructor waits for a second and
        raises a Runtime error because it tries to lock the file for reading by default
        """
        yacmap = yacman.YacAttMap(filepath=cfg_file, writable=True)
        yacman.YacAttMap(filepath=cfg_file, skip_read_lock=True)
        yacmap.make_readonly()

    def test_locking_is_opt_in(self, cfg_file, locked_cfg_file):
        """
        this tests backwards compatibility, in the past the locking system did not exist.
        Consequently, to make yacman backwards compatible, multiple processes should be able to read and write to
        the file when no arguments but the intput are specified
        """
        yacman.YacAttMap(filepath=cfg_file)
        assert not os.path.exists(locked_cfg_file)

    def test_on_init_file_update(self, cfg_file):
        a, v = "testattr", "testval"
        y = yacman.YacAttMap(entries={a: v}, filepath=cfg_file)
        assert y[a] == v

    def test_init_with_empty_file(self, data_path):
        a, v = "testattr", "testval"
        empty_file_path = os.path.join(data_path, "empty_file.yaml")
        open(empty_file_path, "a").close()
        y = yacman.YacAttMap(entries={a: v}, filepath=empty_file_path)
        assert a in y
        os.remove(empty_file_path)


class TestContextManager:
    @pytest.mark.parametrize("state", [True, False])
    def test_context_manager_does_not_change_state(self, cfg_file, state):
        yacmap = yacman.YacAttMap(filepath=cfg_file, writable=state)
        with yacmap as _:
            pass
        is_ro = getattr(yacmap[IK], RO_KEY, None)
        is_writable = None if is_ro is None else not is_ro
        assert is_writable == state

    @pytest.mark.parametrize("state", [True, False])
    def test_context_manager_saves_updates(self, cfg_file, state):
        yacmap = yacman.YacAttMap(filepath=cfg_file, writable=state)
        with yacmap as y:
            y.testattr = "testval"
        if not getattr(yacmap[IK], RO_KEY, True):
            yacmap.make_readonly()
        yacmap1 = yacman.YacAttMap(filepath=cfg_file, writable=True)
        assert yacmap1.testattr == "testval"
        del yacmap1["testattr"]
        yacmap1.make_readonly()

    def test_context_works_with_objects_created_from_entries_with_filepath(
        self, cfg_file
    ):
        yacmap = yacman.YacAttMap(entries={})
        setattr(yacmap[IK], yacman.FILEPATH_KEY, cfg_file)
        with yacmap as _:
            pass

    def test_context_errors_with_objects_created_from_entries(self, cfg_file):
        """Test for TypeError raised in case no valid filepath is set but write requested"""
        yacmap = yacman.YacAttMap(entries={})
        with pytest.raises(TypeError):
            with yacmap as _:
                pass


yaml_str = """\
---
one: 1
2: two
"""


def test_float_idx():
    data = yacman.YacAttMap(yamldata=yaml_str)
    # We should be able to access this by string, not by int index.
    assert data["2"] == "two"
    with pytest.raises(KeyError):
        data[2]


class TestSelectConfig:
    def test_select_config_works_with_filepath(self, cfg_file):
        assert isinstance(yacman.select_config(config_filepath=cfg_file), str)

    def test_select_config_works_env_vars(self, cfg_file, varname="TEST"):
        os.environ[varname] = cfg_file
        assert isinstance(yacman.select_config(config_env_vars=varname), str)
        assert yacman.select_config(config_env_vars=varname) == yacman.select_config(
            config_filepath=cfg_file
        )
        del os.environ[varname]

    def test_select_config_returns_default_cfg(self, path="path.yaml"):
        assert yacman.select_config(default_config_filepath=path) == path

    def test_select_config_returns_none_if_no_cfg_found(self, varname="TEST"):
        os.environ[varname] = "bogus/path.yaml"
        assert yacman.select_config(config_env_vars=varname) is None
        del os.environ[varname]

    def test_select_config_errors_if_no_cfg_found_and_strict_checks_requested(
        self, varname="TEST"
    ):
        os.environ[varname] = "bogus/path.yaml"
        with pytest.raises(Exception):
            yacman.select_config(config_env_vars=varname, strict_env=True)
        del os.environ[varname]


class TestValidation:
    def test_validation_in_constructor(self, cfg_file, schema):
        """test object that adheres to the schema guidelines passes validation"""
        yacman.YacAttMap(filepath=cfg_file, schema_source=schema)

    @pytest.mark.parametrize("value", [1, 2, [1, 2, 3], {"test": 1}])
    def test_validation_fails_in_constructor(self, schema, value):
        """
        test object that does not adhere to the schema
        guidelines does not pass validation
        """
        with pytest.raises(ValidationError):
            yacman.YacAttMap(entries={"testattr": value}, schema_source=schema)

    def test_validation_in_write(self, cfg_file, schema):
        """
        test object that adheres to the schema guidelines passes
        validation on write
        """
        y = yacman.YacAttMap(
            filepath=cfg_file, schema_source=schema, write_validate=True, writable=True
        )
        y.write()

    @pytest.mark.parametrize("value", [1, 2, [1, 2, 3], {"test": 1}])
    def test_validation_fails_in_write(self, cfg_file, schema, value):
        """
        test object that does not adhere to the schema guidelines does not pass
         validation on write
        """
        y = yacman.YacAttMap(
            filepath=cfg_file, schema_source=schema, write_validate=True, writable=True
        )
        y["testattr"] = value
        with pytest.raises(ValidationError):
            y.write()


def cleanup_locks(lcks):
    if lcks:
        [os.remove(l) for l in lcks]


def make_cfg_file_path(name, data_path):
    return os.path.join(data_path, name)


def make_lock_path(name, data_path):
    return os.path.join(data_path, yacman.LOCK_PREFIX + name)

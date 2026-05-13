import importlib
import pkgutil
import pathlib

package_dir = pathlib.Path(__file__).parent
for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
    if module_name != "__init__":
        importlib.import_module(f".{module_name}", package=__name__)
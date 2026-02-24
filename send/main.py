from abc import ABC, abstractmethod
from typing import Generator, Any
import copy
from dataclasses import dataclass
import argparse
import csv

from tabulate import tabulate

# [1] АРГУМЕНТЫ КОМАНДНОЙ СТРОКИ:

def get_args():
    parser = argparse.ArgumentParser(description='Программа анализа данных')
    # Флаги:
    parser.add_argument("-f", "--files", nargs="+", required=True)
    parser.add_argument(
        "-r",
        "--report",
        choices=["average-gdp"],
        help="Доступные типы отчетов: %(choices)s")

    return vars(parser.parse_args())


# Вот тут должен быть блок кода, который на основании данных из флагов занимается
# сопоставлением разных имен полей:
@dataclass
class FieldConfig:
    """
    file_name - имя столбца в файле.
    internal_name - имя в коде готовых report методов.
    display_name - имя в заголовке, в финальном выводе.
    """
    file_name: str
    internal_name: str
    display_name: str

names_config = [
    FieldConfig(file_name = "gdp", internal_name = "gdp", display_name = "gdp"),
    FieldConfig(file_name = "country", internal_name = "country", display_name = "country"),
    FieldConfig(file_name = "gdp", internal_name = "gdp", display_name = "gdp"),
]


# [2] ЗАГРУЗКА:

class ABCLoader():
    """
    Интерфейс и часть кода,
    общая для всех конкретных стратегий-подклассов скачивания данных.
    """
    DEFAULT_ENCODING: str = "utf-8"
    DEFAULT_SEPARATOR: str = ","

    def __init__(
        self,
        reader_factory,
        files: list[str],
        encoding: str = None,
        separator: str = ","):
        """
        Собирает все, что необходимо для скачивания информации из файлов.
        """
        self.encoding = encoding or self.DEFAULT_ENCODING
        self.separator = separator or self.DEFAULT_SEPARATOR

        self.reader_factory = reader_factory
        self.files = files

    # Аннотация - генератор:
    # dict[str, str] - генерирует (yield) словари, ключи и значения которого - это строки, 
    # None - не получет ничего.
    # None - возвращает (return) None.
    def execute(self)-> Generator[dict[str, str], None, None]:
        """
        Делает и вызывает генератор, который по строкам читает файл.
        Код не дублируется в подклассах, 
        """
        for file_name in self.files:
            try:
                with open(file_name, mode="r", encoding = self.encoding) as f:
                    yield from self.reader_factory(f)
            # В ТЗ не было точно указанно, 
            # что делать в случае ошибок, поэтому сделал заготовку:
            except FileNotFoundError:
                # Завершение программы, пропуск файла, или другие действия.
                print(f"\n\nОшибка: Файл {file_name} не найден.\n\n")
            except Exception as e:
                print(f"Ошибка: Не получилось открыть файл {file_name}")
                raise


class CSVDictLoader(ABCLoader):
    """
    Чтение из CSV файла, строки файла - это словари.
    """

    def __init__(self, files: list[str], encoding: str = None, separator: str = None):
        """
        Вот тут весь код, который нужен именно при использовании csv.DictReader:
        """
        # Можно следать
        # import csv
        # сдесь, если у нас будет 10, 20, 30 разных классов загружчиков, и
        # у каждого своя библиотека, при этом метод заргузки выполняется 1 раз.

        encoding = encoding or self.DEFAULT_ENCODING
        separator = separator or self.DEFAULT_SEPARATOR

        # lambda позволяет создать вызываемый объект, передав аргументы в вызов,
        # но отложить сам вызов, т.е. выполнение, до тех пор, пока не будет вызвана 
        # сама lambda:   factory(f).
        reader_factory = lambda f: csv.DictReader(f, delimiter = separator)

        super().__init__(
            reader_factory = reader_factory,
            files = files,
            encoding = encoding,
            separator = separator
            )


# [3] ТРАНСФОРМЕРЫ:

class ABCTransformer(ABC):
    """
    Интерфейс и шаблонный метод для всех конкретных классов-стратегий фильтрации данных.
    Любой класс трансформер принимает фабрику генераторов на вход и возвращает генератор.
    Удаление ненужных полей в записях (чтобы меньше весили) или фильтарция записей
    по условию.
    """
    @abstractmethod
    def __init__(self):
        # Аргументы вроде get_fields, add_fields, where, between и тому подобное.
        pass

    @abstractmethod
    def execute(self)-> Generator:
        pass

    def generate_all(self):
        """
        Трансформер прогоняет через себя все данные.
        """
        for _ in self.execute():
            pass

class CutFieldsTransformer(ABCTransformer):
    """
    Отсекает ненужные поля в строках.
    Использовать, когда большинство полей нужны - быстрее удалить не нужное,
    а так же меньше перечислять в cut_fields.
    """
    def __init__(
        self,
        loader_factory: ABCLoader | ABCTransformer,
        cut_fields: list[str],
        ):
        """
        loader_factory - это то, что создает генераторы,
        чтобы можно было использовать много раз.
        """
        self.loader_factory = loader_factory
        self.cut_fields = cut_fields

    def execute(self)-> Generator:
        for row in self.loader_factory.execute():
            for field in self.cut_fields:
                row.pop(field, None)
            yield row

class GetFieldsTransformer(ABCTransformer):
    """
    Создает словарь только из нужных полей.
    Использовать, когда большинство полей не нужны:
    быстрее создать новый словарь, а так же меньше перечислять в get_fields.
    """
    def __init__(
        self,
        loader_factory:  ABCLoader | ABCTransformer,
        # get_fileds - это set, а не list, чтобы k in self.get_fileds был за O(1).
        get_fields: set[str],
        ):
        self.loader_factory = loader_factory
        self.get_fields = get_fields

    def execute(self)-> Generator:
        for row in self.loader_factory.execute():
            yield {k: v for k, v in row.items() if k in self.get_fields}


class RenameFieldsTransformer(ABCTransformer):
    """
    Меняет имена-ключи словарей.
    """
    def __init__(self, loader_factory, fields_config: list[FieldConfig]):
        self.loader_factory = loader_factory
        # Создаем словарь для быстрой замены {'file_name': 'internal_name'}:
        self.mapping = {f.file_name: f.internal_name for f in fields_config}

    def execute(self) -> Generator:
        for row in self.loader_factory.execute():
            # Создаем новый словарь, заменяя только те ключи, что есть в маппинге,
            # заменять ключи быстрее, чем создавать новые словари.
            yield {self.mapping.get(k, k): v for k, v in row.items()}

# [4] МЕТРИКИ:

class ABCMetric(ABC):
    """
    Интерфейс для всех конкретных классов-функций по обработке данных.
    """
    @abstractmethod
    def __init__(self):
        """
        Храним результаты обработки записей. 
        """
        pass
    @abstractmethod
    def update(self, row: dict):
        """
        Получаем по одной записи для обработки.
        """
        pass
    @abstractmethod
    def get_result(self) -> dict[str, Any]:
        """
        Выдаем результат после обработки всех записей.
        """
        pass


class SumMetric(ABCMetric):
    """
    Суммирует значения полей из всех записей.
    """
    def __init__(self, sum_fields: list[str]):
        self.sum_fields = sum_fields
        self.total_dict = {field: 0.0 for field in sum_fields}

    def update(self, row: dict):
        for f in self.sum_fields:
            try:
                # Ключа нет - 0 or 0, будет 0.
                # Ключ есть, но значение это "" или None - None or 0 или "" or 0, будет 0. 
                self.total_dict[f] += float(row.get(f, 0) or 0)
            except (ValueError, TypeError):
                pass

    def get_result(self)-> dict[str, float]:
        return self.total_dict


class CountMetric(ABCMetric):
    """
    Считает количество строк.
    """
    # Будет всегда считать количество словарей, даже если в них "битые" данные,
    # если программа должна работать с битыми данными, то тогда потребуются 
    # четкие инструкции, что с ними делать, а так же дополнительные классы.
    def __init__(self):
        self.count_dict = {"count": 0}

    def update(self, row: dict):
        self.count_dict["count"] += 1

    def get_result(self)-> dict[str, int]:
        return self.count_dict

# [5] ПРОЦЕССОРЫ:

class ABCProcessor(ABC):
    """
    Интерфейс, общий для всех процессов.
    """
    def __init__(self):
        pass
        # metrics это list[ABCMetric], передаем объекты.

    @abstractmethod
    def execute(self):
        """Запуск процесса обработки данных."""
        pass

    def generate_all(self):
        """
        Генератор прогоняет через себя все данные.
        """
        for _ in self.execute():
            pass

    @abstractmethod
    def get_data(self)-> tuple(list[str]):
        """Возвращает (rows, headers) для вывода данных."""
        pass


class Processor(ABCProcessor):
    """
    Получает по одной записи из генератора и возвращает генератор записей,
    сам ничего не делает, по для каждой записи вызывает метод update из всех
    подключенных метрик.
    """
    def __init__(
        self,
        loader_factory: ABCLoader | ABCTransformer,
        metrics: list[ABCMetric]
        ):
        self.loader_factory = loader_factory
        self.metrics = metrics

    def execute(self):
        """
        Вызвать общий интерфейс для каждой метрики.
        """
        for row in self.loader_factory():
            for metric in self.metrics:
                metric.update(row)
            yield row

    def get_data(self):
        headers = []
        row_data = []

        for m in self.metrics:
            res = m.get_result()

            headers.extend(res.keys())
            row_data.extend(res.values())
        
        return (row_data, headers)

class GroupProcessor(ABCProcessor):
    """
    Группирует записи по комбинации полей.
    """

    def __init__(
        self,
        loader_factory: ABCLoader | ABCTransformer,
        metrics: list[ABCMetric],
        group_fields: list[str],
        ):
        self.loader_factory = loader_factory
        self.metrics = metrics
        self.group_fields = group_fields
        self.groups: dict[tuple, list[ABCMetric]] = dict()

    def execute(self):
        for row in self.loader_factory.execute():
            # Создаем название для группировки - кортеж из комбинаций имен столбцов:
            group_key = tuple(row[f] for f in self.group_fields)

            if group_key not in self.groups:
                # Создаем независимую копию объектов метрик каждой группы:
                self.groups[group_key] = [copy.deepcopy(m) for m in self.metrics]

            # Вызываем метрики: 
            for metric in self.groups[group_key]:
                metric.update(row)

            yield row

    def get_data(self):

        # Заголоки -  
        metric_headers = []

        for m in self.metrics:
            metric_headers.extend(m.get_result().keys())

        all_headers = list(self.group_fields) + metric_headers
        table_rows = []

        for key, group_metrics in self.groups.items():
            # Формируем словарь для строки: сначала поля группировки:
            row_dict = dict(zip(self.group_fields, key))
            
            # Затем добавляем данные из каждой метрики:
            for m in group_metrics:
                row_dict.update(m.get_result())

            table_rows.append(row_dict)
            
        return table_rows, all_headers


# [6] СОЗДАТЕЛЬ ОТЧЕТОВ:

class ReportApp:

    def __init__(
        self,
        args: dict,
        names_config: list[FieldConfig] = names_config,
        download_factory: ABCLoader = CSVDictLoader,
        ):
        """
        Данные хранятся в одном месте, если потребуеся создать несколько разных
        отчетов на основе одних и тех же данных.
        """
        self.files = args.get("files")
        self.report_type = args.get("report")
        self.names_config = names_config

        self.download_factory = CSVDictLoader(files = self.files)
        self.loader_factory = RenameFieldsTransformer(
            loader_factory = self.download_factory,
            fields_config = self.names_config,
            )

    def execute(self):
        """
        Выполнение отчета.
        """
        # Каждый метод, соотвествующий значению флага report, имеет название,
        # повторяющее название значение флага, но с report_ вначале.
        # Более простая альтернатива - вручную прописать словарь, где ключ - 
        # это имя метода, а значение - метод и атрибуты:
        method_name = f"report_{self.report_type.replace('-', '_')}"
        if hasattr(self, method_name):
            getattr(self, method_name)()
        else:
            print(f"Ошибка: Отчет '{self.report_type}' не реализован.")

    def report_average_gdp(self):
        """
        Отчет - среднее ВВП по странам.
        Имена полей:
        'country' и 'gdp'
        """
        # Сейчас это можно не использвать, но если в программе появятся флаги для
        # изменения имен (пример - разные языки), то это будет нужно:
        display_names = {f.internal_name: f.display_name for f in self.names_config}

        filter_data = GetFieldsTransformer(
            loader_factory = self.loader_factory,
            get_fields = ["gdp", "country"],
            )

        # Метрики:
        metrics = [
            SumMetric(sum_fields = ["gdp"]),
            CountMetric(),
        ]

        # Группируем по странам:
        processor = GroupProcessor(
            loader_factory = filter_data,
            metrics = metrics,
            group_fields = ["country"],
        )

        # Прогнать данные:
        processor.generate_all()

        # Получаем данные:
        # Формат table_rows: [{"Поле_таблицы_1": value, "Поле_таблицы_2": value}, ...]
        dict_rows, _ = processor.get_data()

        final_data = []

        # Вычисляем среднее:
        for row in dict_rows:
            average_gdp = row["gdp"] / row["count"] if row["count"] > 0 else 0

            final_data.append({
                display_names["country"]: row["country"],
                display_names["gdp"]: average_gdp,
            })

        # Сортировка:
        final_data.sort(key = lambda x: x[display_names["gdp"]], reverse = True)

        index_range = range(1, len(final_data) + 1)

        # Вывод:
        print(
            tabulate(
                final_data,
                headers = "keys",
                showindex = index_range,
                tablefmt="grid", 
                floatfmt=".2f"
                )
        )

# ТОЧКА ВХОДА:

# Для корректной работы, когда этот файл импортируют:
if __name__ == "__main__":
    args = get_args()
    app = ReportApp(args)
    app.execute()
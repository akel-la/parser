import sys
from typing import Generator
import pytest

from tabulate import tabulate

from main import (
    ReportApp,
    SumMetric,
    CountMetric,
    get_args,
    CutFieldsTransformer,
    GetFieldsTransformer,
    RenameFieldsTransformer,
    FieldConfig,
)

# ОБЩИЕ ФИКСТУРЫ:

@pytest.fixture
def get_data():
    """
    Возвращает словарь с исходными данными и заранее вычисленными правильными
    ответами для проверки.
    """
    # Добавляем данные:
    raw_rows = [
        {'country': 'United States', 'year': '2023', 'gdp': '25462',
        'gdp_growth': '2.1', 'inflation': '3.4', 'unemployment': '3.7',
        'population': '339', 'continent': 'North America'},
        {'country': 'United States', 'year': '2022', 'gdp': '23315',
        'gdp_growth': '2.1', 'inflation': '8.0', 'unemployment': '3.6',
        'population': '338', 'continent': 'North America'},
        {'country': 'United States', 'year': '2021', 'gdp': '22994',
        'gdp_growth': '5.9', 'inflation': '4.7', 'unemployment': '5.3',
        'population': '337', 'continent': 'North America'},
        {'country': 'China', 'year': '2023', 'gdp': '17963',
        'gdp_growth': '5.2', 'inflation': '2.5', 'unemployment': '5.2',
        'population': '1425', 'continent': 'Asia'},
        {'country': 'China', 'year': '2022', 'gdp': '17734',
        'gdp_growth': '3.0', 'inflation': '2.0', 'unemployment': '5.6',
        'population': '1423', 'continent': 'Asia'},
        {'country': 'China', 'year': '2021', 'gdp': '17734',
        'gdp_growth': '8.4', 'inflation': '1.0', 'unemployment': '5.1',
        'population': '1420', 'continent': 'Asia'},
        {'country': 'Germany', 'year': '2023', 'gdp': '4086',
        'gdp_growth': '-0.3', 'inflation': '6.2', 'unemployment': '3.0',
        'population': '83', 'continent': 'Europe'},
        {'country': 'Germany', 'year': '2022', 'gdp': '4072',
        'gdp_growth': '1.8', 'inflation': '8.7', 'unemployment': '3.1',
        'population': '83', 'continent': 'Europe'},
    ]
    # Расчитываем метаданные:
    row_count = len(raw_rows)

    gdp_sum = sum(float(row["gdp"]) for row in raw_rows)
    inflation_sum = sum(float(row["inflation"]) for row in raw_rows)
    unemployment_sum = sum(float(row["unemployment"]) for row in raw_rows)

    # Добавляем метаданные в ответ:
    return {
        "raw_data": raw_rows,
        "count": {"count": row_count},
        "sum": {
            "gdp": gdp_sum,
            "inflation": inflation_sum,
            "unemployment": unemployment_sum,
        },
        "average": {
            "gdp": gdp_sum / row_count,
            "inflation": inflation_sum / row_count,
            "unemployment": unemployment_sum / row_count,
        }
    }


# ТРАНСФОРМЕРЫ:

# Объект заглушка, имитирующий loader factory:
class MockLoader:

    def __init__(self, data):
        self.data = data

    def execute(self)-> Generator:
        for row in self.data:
            # В тестах возрващаем копию, чтобы не портить исходник:
            yield row.copy()


def test_cut_fields_transformer():
    data = [
        {"a": 1, "b": 2, "c": 3},
        {"a": 4, "b": 5, "c": 6},
    ]
    loader = MockLoader(data)

    transformer = CutFieldsTransformer(loader, cut_fields=["a", "c", "d"])

    result = list(transformer.execute())

    # Есть нужное:
    assert result == [{"b": 2}, {"b": 5}]

    # Нету не нужного:
    for field in ["a", "c", "d"]:
        assert field not in result[0]
        assert field not in result[1]


def test_get_fields_transformer():
    data = [
        {"a": 1, "b": 2, "c": 3},
        {"a": 4, "b": 5, "c": 6},
    ]
    loader = MockLoader(data)

    transformer = GetFieldsTransformer(loader, get_fields=["a", "d"])

    result = list(transformer.execute())

    # Есть нужное:
    assert result == [{"a": 1}, {"a": 4}]

    # Нету не нужного:
    for field in ["b", "c"]:
        assert field not in result[0]
        assert field not in result[1]


def test_rename_fields_transformer():
    data = [
        {"file a": 11, "file b": 12, "file c": 13},
        {"file a": 21, "file b": 22, "file c": 23},
    ]

    loader = MockLoader(data)

    names_config = [
    FieldConfig(file_name = "file a", internal_name = "int a", display_name = "dis a"),
    FieldConfig(file_name = "file b", internal_name = "int b", display_name = "dis b"),
    FieldConfig(file_name = "int c", internal_name = "int c", display_name = "dis c"),
    ]
    transformer = RenameFieldsTransformer(loader, names_config)

    result = list(transformer.execute())

    assert result, [
        {"int a": 11, "int b": 12, "int c": 13},
        {"int a": 21, "int b": 22, "int c": 23},
        ]



# МЕТРИКИ:


def test_sum_metric_one_fileld(get_data):
    """
    Тест с одним полем.
    """
    metric = SumMetric(sum_fields = ["inflation"])

    for row in get_data["raw_data"]:
        metric.update(row)

    result = metric.get_result()
    assert result["inflation"] == pytest.approx(get_data["sum"]["inflation"])


def test_sum_metric_many_filelds(get_data):
    """
    Тест с несколькими полями.
    """
    metric = SumMetric(sum_fields = ["gdp", "unemployment"])

    for row in get_data["raw_data"]:
        metric.update(row)

    result = metric.get_result()
    assert result["gdp"] == pytest.approx(get_data["sum"]["gdp"])
    assert result["unemployment"] == pytest.approx(get_data["sum"]["unemployment"])


def test_sum_metric_uncorrect_data():
    metric = SumMetric(sum_fields = ["gdp"])
    # Корректные данные:
    metric.update({"gdp": "100.5"})
    metric.update({"gdp": "52.54"})
    metric.update({"gdp": "13.9"})
    # Не корректные данные:
    metric.update({"gdp": ""})
    metric.update({"gdp": "Не число"})
    # pytest.approx - сравнивает float с небольшой погрешностью:
    assert metric.get_result()["gdp"] == pytest.approx(166.94)


def test_count_metric(get_data):
    metric = CountMetric()

    for row in get_data["raw_data"]:
        metric.update(row)

    assert metric.get_result() == get_data["count"]


def test_count_metric_uncorrect_data():
    metric = CountMetric()
    metric.update({"gdp": "100.5"})
    # Не корректные данные:
    metric.update({"gdp": ""})
    metric.update({"gdp": "Не число"})
    assert metric.get_result() == {"count": 3}

# ПОДГОТОВКА К ТЕСТАМ С ФАЙЛАМИ:

@pytest.fixture
def test_files(tmp_path):
    """
    Создаем временные каталог и CSV файлы в нем.
    """
    # tmp_path / str - это прибавление str к пути, если tmp_path - это объект
    # типа path (переопределенный для этого типа оператор деления). Разделитель 
    # подставляется исходя из ОС.
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    file_1 = data_dir / "test_file_1.csv"
    file_1.write_text(
        "country,year,gdp,gdp_growth,inflation,unemployment,population,continent\n"
        "Mexico,2023,1490,3.2,4.7,2.9,128,North America\n"
        "Mexico,2022,1414,3.9,7.9,3.3,127,North America\n"
        "Mexico,2021,1274,5.7,5.7,4.1,126,North America\n"
        "Indonesia,2023,1319,5.0,3.0,5.3,278,Asia\n"
        "Indonesia,2022,1318,5.3,4.2,5.5,276,Asia\n"
        "Indonesia,2021,1186,3.7,1.6,6.3,275,Asia\n"
        "Netherlands,2023,991,0.1,4.1,3.5,18,Europe\n"
        "Netherlands,2022,1009,4.3,11.6,3.6,18,Europe\n"
        "Netherlands,2021,1018,4.9,2.7,3.8,17,Europe\n"
    )
    
    file_2 = data_dir / "test_file_2.csv"
    file_2.write_text(
        "country,year,gdp,gdp_growth,inflation,unemployment,population,continent\n"
        "France,2023,2788,0.7,5.7,7.1,68,Europe\n"
        "France,2022,2779,2.5,5.9,7.4,68,Europe\n"
        "France,2021,2937,6.8,1.6,7.9,68,Europe\n"
        "Brazil,2023,2173,2.9,4.6,8.5,216,South America\n"
        "Brazil,2022,1920,2.9,9.3,9.3,215,South America\n"
        "Brazil,2021,1609,5.0,8.3,13.2,214,South America\n"
    )

    return [str(file_1), str(file_2)]


def get_expected_table(data):
    """
    Вывод в нужном формате.
    """
    return tabulate(
        data,
        headers="keys",
        showindex=range(1, len(data) + 1),
        tablefmt="grid",
        floatfmt=".2f"
    ).strip()

# ТЕСТ ВСЕЙ ПРОГРАММЫ (End to End):

# Ожидаемые ответы:
# mark.parametrize - декоратор, выполняет функцию множество раз,
# подставяя разные данные.
@pytest.mark.parametrize("file_indices, expected_answer", [
    # Тест с одним файлом:
    ([0], [
        {'country': 'Mexico', 'gdp': 1392.6666666666667}, 
        {'country': 'Indonesia', 'gdp': 1274.3333333333333}, 
        {'country': 'Netherlands', 'gdp': 1006.0},      
    ]),
    # Тест с двумя файлами:
    ([0, 1], [
        {'country': 'France', 'gdp': 2834.6666666666665}, 
        {'country': 'Brazil', 'gdp': 1900.6666666666667}, 
        {'country': 'Mexico', 'gdp': 1392.6666666666667}, 
        {'country': 'Indonesia', 'gdp': 1274.3333333333333}, 
        {'country': 'Netherlands', 'gdp': 1006.0},      
    ])
])

# tmp_path, capsys, monkeypatch - специальные имена для pytest,
# pytest подставляет нужные значения. Не переименовывать. Назначение:
# tmp_path - создает временную папку.
# capsys - перехват вывода данных.
# monkeypatch - динамическая подмена (в контексте теста - подмена sys.argv)
def test_full_program_logic(test_files, tmp_path, capsys, monkeypatch, file_indices, expected_answer):
    # Берем из pytest.mark.parametrize файлы по индексам:
    selected_files = [test_files[i] for i in file_indices]

    # Собираем аргументы коммандной строки:
    test_argv = ["main.py", "--files"] + selected_files + ["--report", "average-gdp"]
    monkeypatch.setattr(sys, "argv", test_argv)

    # Выполнение:
    args = get_args()
    app = ReportApp(args)
    app.execute()

    # Проверка:

    # readouterr - забирает все,
    # что программа успела "вывести" в stdout и stderror.
    # strip() уберет лишние переносы строк:
    actual_output = capsys.readouterr().out.strip()
    assert actual_output == get_expected_table(expected_answer)
    




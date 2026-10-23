"""发布前自检脚本（无需 pytest，直接运行）::

    set PYTHONPATH=src
    python tests/run_checks.py          # 离线功能自检
    python tests/run_checks.py --online # 附加在线 COD 实测（需联网）

覆盖：CIF 解析（对称操作数值验证 / esd 剥离 / 分号多行块）、
MP structure → CIF、本地库检索过滤（COD 索引 / polyDB / xinDB）、
明亮模式主题与帮助菜单、3D 渲染、注册机制链路、GUI 离屏冒烟。

配置隔离：自检在独立临时配置目录中进行（POLYXRD_GETCIF_CONFIG_DIR），
不读写用户真实 settings.toml。
"""
from __future__ import annotations

import gzip
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 自检隔离：配置目录指向临时目录，避免污染用户真实 settings.toml
# （必须在任何 getcif 模块导入/调用前设置；config.app_config_dir 每次调用时读取）
_CONFIG_ISOLATION = os.environ.setdefault(
    "POLYXRD_GETCIF_CONFIG_DIR",
    str(Path(tempfile.mkdtemp(prefix="getcif-checks-"))),
)

SAMPLE_CIF = """data_1010921
_cell_length_a 4.9134
_cell_length_b 4.9134
_cell_length_c 5.4052
_cell_angle_alpha 90.0
_cell_angle_beta 90.0
_cell_angle_gamma 120.0
_cell_volume 113.0
_chemical_formula_sum 'O2 Si'
_symmetry_space_group_name_H-M 'P 32 2 1'
loop_
_symmetry_equiv_pos_as_xyz
'x, y, z'
'-y, x-y, z+2/3'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Si1 Si 0.4697 0.0000 0.0000
O1 O 0.4135 0.2669 0.1191
"""

REAL_STYLE_CIF = """# comment header
data_1010921
loop_
_publ_author_name
'Barth, T F W'
_publ_section_title
;
The Cristobalite Structures. I. High-Cristobalite
;
_chemical_formula_sum            'O2 Si'
_space_group_IT_number           198
_symmetry_space_group_name_H-M   'P 21 3'
_cell_angle_alpha                90
_cell_angle_beta                 90
_cell_angle_gamma                90
_cell_length_a                   7.16
_cell_length_b                   7.16
_cell_length_c                   7.16
loop_
_symmetry_equiv_pos_as_xyz
'x, y, z'
'1/2-z,-x,1/2+y'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_symmetry_multiplicity
_atom_site_Wyckoff_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Si1 Si4+ 4 a 0.255(8) 0.255(8) 0.255(8) 1.
O2 O2- 12 b 0.660(15) 0.660(15) 0.062(15) 1.
"""


def check(name: str, condition: bool, detail: str = "") -> None:
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {name}" + (f"  ({detail})" if detail else ""))
    if not condition:
        raise SystemExit(f"自检失败：{name}")


def test_cif_parse() -> None:
    from getcif.cifparse import parse_cif

    cif = parse_cif(SAMPLE_CIF)
    check("CIF 晶胞解析", abs(cif.cell["a"] - 4.9134) < 1e-6)
    check("CIF 化学式", cif.formula == "O2 Si")
    check("对称操作条数", len(cif.symmetry_ops) == 2)
    check("位点条数", len(cif.sites) == 2)
    check("晶胞体积", abs(cif.volume - 113.0) < 1.0)
    op = cif.symmetry_ops[1]
    x, y, z = 0.4697, 0.0, 0.0
    gx = op[0] * x + op[1] * y + op[2] * z + op[3]
    gy = op[4] * x + op[5] * y + op[6] * z + op[7]
    gz = op[8] * x + op[9] * y + op[10] * z + op[11]
    check("对称操作数值", abs(gx) < 1e-9 and abs(gy - 0.4697) < 1e-9 and abs(gz - 2 / 3) < 1e-3)

    real = parse_cif(REAL_STYLE_CIF)
    check("真实风格 CIF 晶胞", abs(real.cell["a"] - 7.16) < 1e-9)
    check("esd 剥离（0.255(8)）", abs(real.sites[0]["x"] - 0.255) < 1e-9)
    check("元素提取（Si4+→Si）", real.sites[0]["element"] == "Si")
    check("分号多行块跳过", real.formula == "O2 Si")


def test_mp_structure_to_cif() -> None:
    from getcif.cifparse import cif_from_structure, parse_cif

    mp_struct = {
        "lattice": {"a": 5.47, "b": 5.47, "c": 5.47, "alpha": 90, "beta": 90,
                    "gamma": 90, "volume": 163.7},
        "sites": [
            {"species": [{"element": "Si", "occu": 1.0}], "abc": [0.0, 0.0, 0.0]},
            {"species": [{"element": "O", "occu": 1.0}], "abc": [0.5, 0.5, 0.0]},
        ],
    }
    text = cif_from_structure(mp_struct, "mp-1234")
    cif = parse_cif(text)
    check("MP structure → CIF", len(cif.sites) == 2 and abs(cif.cell["a"] - 5.47) < 1e-9)


def _make_temp_index() -> Path:
    tmp = Path(tempfile.mkdtemp())
    db_path = tmp / "cod_index.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE cod_entries (
        cod_id INTEGER PRIMARY KEY, file TEXT, mineral_name TEXT, formula TEXT, formula_red TEXT,
        elements TEXT, space_group TEXT, space_group_number INTEGER DEFAULT 0,
        a REAL DEFAULT 0, b REAL DEFAULT 0, c REAL DEFAULT 0,
        alpha REAL DEFAULT 90, beta REAL DEFAULT 90, gamma REAL DEFAULT 90,
        volume REAL DEFAULT 0, cif_gz BLOB)""")
    conn.execute(
        "INSERT INTO cod_entries (cod_id, file, mineral_name, formula, formula_red, elements,"
        " space_group, space_group_number, a,b,c,alpha,beta,gamma, volume, cif_gz)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (1010921, "cifs/1010921.cif", "Quartz", "O2 Si", "O2 Si", "O,Si", "P 32 2 1", 154,
         4.9134, 4.9134, 5.4052, 90, 90, 120, 113.0, gzip.compress(SAMPLE_CIF.encode())))
    conn.commit()
    conn.close()
    return db_path, tmp


def test_cod_local() -> None:
    from getcif.adapters.cod_local import CodLocalAdapter
    from getcif.core import config as cfg
    from getcif.core.schema import SearchQuery

    db_path, tmp = _make_temp_index()
    cfg.save("local", {"db_path": str(db_path), "cod_root": str(tmp)})
    cfg.set_source_enabled("local", True)
    adapter = CodLocalAdapter(timeout=10)
    check("本地库可用性", adapter.is_available())
    cands = adapter.search(SearchQuery(formula="SiO2", limit=10))
    check("本地库化学式检索", len(cands) == 1 and cands[0].source_id == "1010921")
    text = adapter.download_cif(cands[0])
    check("本地库 cif_gz 取回", bool(text) and "data_1010921" in text)
    check("本地库元素过滤", len(adapter.search(SearchQuery(elements="Si", limit=10))) == 1)
    check("本地库名称过滤", len(adapter.search(SearchQuery(name="quartz", limit=10))) == 1)
    check("本地库空间群过滤", len(adapter.search(SearchQuery(space_group="154", limit=10))) == 1)
    check("本地库晶胞过滤", len(adapter.search(SearchQuery(a=4.9, b=4.9, c=5.4, limit=10))) == 1)
    check("本地库晶系过滤（三方）", len(adapter.search(SearchQuery(crystal_system="三方", limit=10))) == 1)
    check("本地库晶系过滤（立方=0）", len(adapter.search(SearchQuery(crystal_system="cubic", limit=10))) == 0)


def _make_temp_polydb() -> tuple[Path, Path]:
    """构造临时 polyDB 目录容器（meta.json + index.sqlite）+ 数据根目录下的 CIF。"""
    tmp = Path(tempfile.mkdtemp())
    db_dir = tmp / "cod-inorg"
    db_dir.mkdir()
    (db_dir / "meta.json").write_text(json.dumps({
        "format": "polyDB", "schema_version": 1, "variant": "cod-inorg",
        "counts": {"phases": 1, "k": 4, "peaks": 4, "sites": 2},
    }), encoding="utf-8")
    conn = sqlite3.connect(db_dir / "index.sqlite")
    conn.execute("""CREATE TABLE entries (
        eid INTEGER PRIMARY KEY, formula TEXT, formula_red TEXT, mineral TEXT,
        space_group TEXT, sg_number INTEGER, elements TEXT,
        a REAL, b REAL, c REAL, alpha REAL, beta REAL, gamma REAL,
        volume REAL, density REAL, z INTEGER, n_peaks INTEGER,
        tier INTEGER DEFAULT 0, dup_group INTEGER DEFAULT 0,
        cif_rel TEXT, src_mtime INTEGER, row_idx INTEGER)""")
    conn.execute(
        "INSERT INTO entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (1010921, "O2 Si", "O2 Si", "Quartz", "P 32 2 1", 154, "O,Si",
         4.9134, 4.9134, 5.4052, 90, 90, 120, 113.0, 2.65, 3, 4, 0, 0,
         "cifs/1010921.cif", 0, 0))
    conn.commit()
    conn.close()
    cif_path = tmp / "cifs" / "1010921.cif"   # cif_rel 相对数据根目录
    cif_path.parent.mkdir(parents=True)
    cif_path.write_text(SAMPLE_CIF, encoding="utf-8")
    return db_dir, tmp


def test_polydb() -> None:
    from getcif.adapters.base import AdapterError
    from getcif.adapters.polydb import PolyDbAdapter, probe_polydb
    from getcif.core import config as cfg
    from getcif.core.schema import SearchQuery

    db_dir, tmp = _make_temp_polydb()
    cfg.save("local", {"polydb_path": str(db_dir), "cod_root": str(tmp)})
    cfg.set_source_enabled("polydb", True)
    ok, reason = probe_polydb(db_dir)
    check("polyDB 目录判别", ok, reason)
    ok2, reason2 = probe_polydb(tmp)   # 数据根目录本身不是 polyDB
    check("polyDB 拒绝非库目录", not ok2 and reason2 == "missing:meta.json", reason2)
    adapter = PolyDbAdapter(timeout=10)
    check("polyDB 可用性", adapter.is_available())
    cands = adapter.search(SearchQuery(formula="SiO2", limit=10))
    check("polyDB 化学式检索", len(cands) == 1 and cands[0].source_id == "1010921")
    text = adapter.download_cif(cands[0])
    check("polyDB cif_rel 取回", bool(text) and "data_1010921" in text)
    check("polyDB 空间群过滤", len(adapter.search(SearchQuery(space_group="154", limit=10))) == 1)
    check("polyDB 晶系过滤（三方）", len(adapter.search(SearchQuery(crystal_system="三方", limit=10))) == 1)
    check("polyDB 晶系过滤（立方=0）", len(adapter.search(SearchQuery(crystal_system="cubic", limit=10))) == 0)
    check("polyDB 名称过滤", len(adapter.search(SearchQuery(name="quartz", limit=10))) == 1)
    cfg.set_source_enabled("polydb", False)
    check("polyDB 关闭后不可用", not adapter.is_available())
    check("polyDB 关闭后原因", "关闭" in adapter.availability_reason(),
          adapter.availability_reason())
    cfg.set_source_enabled("polydb", True)
    check("polyDB 重新开启后可用", adapter.is_available())


def _make_temp_xindb() -> Path:
    """构造临时 xinDB v3 单文件（meta / entries / peak_chunks）。"""
    tmp = Path(tempfile.mkdtemp())
    db_path = tmp / "cod_inorganics.xinDB"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE entries (
            entry_id TEXT PRIMARY KEY, formula TEXT, space_group TEXT,
            crystal_system TEXT, mineral_name TEXT, elements TEXT, elem_mask INTEGER,
            a REAL, b REAL, c REAL, alpha REAL, beta REAL, gamma REAL,
            volume REAL, density REAL, year INTEGER, author TEXT, journal TEXT,
            quality TEXT, n_peaks INTEGER, peak_off INTEGER, peak_n INTEGER,
            tier INTEGER DEFAULT 1);
        CREATE TABLE peak_chunks (
            chunk_id INTEGER PRIMARY KEY, n INTEGER,
            top_d BLOB, top_i BLOB, all_d BLOB, all_i BLOB);
    """)
    conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '3')")
    conn.execute("INSERT INTO meta (key, value) VALUES ('entry_count', '1')")
    conn.execute(
        "INSERT INTO entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("96-101-0921", "O2 Si", "P 32 2 1", "trigonal", "Quartz", "O,Si", 0,
         4.9134, 4.9134, 5.4052, 90, 90, 120, 113.0, 2.65, 2001, "", "", "",
         4, 0, 4, 1))
    conn.execute("INSERT INTO peak_chunks VALUES (0, 1, X'00', X'00', X'00', X'00')")
    conn.commit()
    conn.close()
    return db_path


def test_xindb() -> None:
    from getcif.adapters.base import AdapterError
    from getcif.adapters.xindb import XinDbAdapter, probe_xindb
    from getcif.core import config as cfg
    from getcif.core.schema import SearchQuery

    db_path = _make_temp_xindb()
    cfg.save("local", {"xindb_path": str(db_path)})
    cfg.set_source_enabled("xindb", True)
    ok, reason = probe_xindb(db_path)
    check("xinDB 库判别", ok, reason)
    ok2, reason2 = probe_xindb(db_path.parent)   # 目录不是文件
    check("xinDB 拒绝非文件", not ok2 and reason2 == "not_a_file", reason2)
    adapter = XinDbAdapter(timeout=10)
    check("xinDB 可用性", adapter.is_available())
    cands = adapter.search(SearchQuery(formula="SiO2", limit=10))
    check("xinDB 化学式检索", len(cands) == 1 and cands[0].source_id == "96-101-0921")
    check("xinDB 空间群文本过滤", len(adapter.search(SearchQuery(space_group="P 32 2 1", limit=10))) == 1)
    check("xinDB 晶系过滤（三方）", len(adapter.search(SearchQuery(crystal_system="三方", limit=10))) == 1)
    check("xinDB 晶系直查（trigonal）", len(adapter.search(SearchQuery(crystal_system="trigonal", limit=10))) == 1)
    check("xinDB 晶系过滤（立方=0）", len(adapter.search(SearchQuery(crystal_system="cubic", limit=10))) == 0)
    check("xinDB 晶胞过滤", len(adapter.search(SearchQuery(a=4.9, b=4.9, c=5.4, limit=10))) == 1)
    try:
        adapter.download_cif(cands[0])
        check("xinDB 无 CIF 原文（应抛 AdapterError）", False)
    except AdapterError:
        check("xinDB 无 CIF 原文（应抛 AdapterError）", True)


def test_theme_and_help_menu() -> None:
    """明亮模式主题 + 帮助菜单「版权与许可」。"""
    from PySide6.QtWidgets import QApplication

    from getcif.ui.main_window import MainWindow
    from getcif.ui.theme import BG, build_qss

    qss = build_qss()
    check("明亮模式底色（#F2F5F8）", BG == "#F2F5F8" and "#F2F5F8" in qss)
    check("明亮模式不含暗黑底色", "#0B1524" not in qss and "#101E31" not in qss)

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    help_menu = None
    for action in window.menuBar().actions():
        if action.menu() is not None and action.text() == "帮助 (&H)":
            help_menu = action.menu()
    check("帮助菜单存在", help_menu is not None)
    if help_menu is not None:
        texts = [a.text() for a in help_menu.actions()]
        check("帮助菜单含「版权与许可」", "版权与许可 (&L)" in texts, str(texts))
        check("帮助菜单含「关于」", any(t.startswith("关于") for t in texts), str(texts))
    window.close()


def test_viewer() -> None:
    from PySide6.QtWidgets import QApplication

    from getcif.cifparse import parse_cif
    from getcif.viz3d import Viewer3D

    app = QApplication.instance() or QApplication([])
    viewer = Viewer3D()
    check("3D 控件构造", viewer.widget is not None)
    ok = viewer.set_cif(parse_cif(SAMPLE_CIF), label="selftest")
    check("3D 渲染", ok, viewer.last_message)


def test_registration() -> None:
    """注册机制链路：未注册初始态 → 开发方生成注册码 → 保存/刷新 → 状态栏文案 → 防篡改。"""
    import json

    from getcif.utils import registration

    with tempfile.TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "registration.json"

        manager = registration.RegistrationManager("PolyXRD-GetCIF", state_path)
        check("注册初始态（未注册）", not manager.state.registered)
        check("状态栏文案（未注册）", manager.label(None).text() == "未注册")

        # 模拟开发方根据「单位部门名称」生成注册码（make_reg_code.py 同逻辑）
        unit = "某某大学材料科学与工程学院"
        code = registration.generate_code(unit)
        check("注册码格式", code.startswith("PXRD1-"))
        check("注册码校验还原单位名", registration.verify_code(code) == unit)
        check("注册码容错（小写+空格）",
              registration.verify_code(code.lower().replace("-", " ")) == unit)
        check("无效注册码拒绝", registration.verify_code("PXRD1-GARBAGE") is None)

        # 模拟用户在「输入注册码」对话框确认后的落盘
        state = registration.save_state(state_path, code)
        check("注册状态保存", state.registered and state.unit == unit)
        manager.refresh()
        check("管理器刷新为已注册", manager.state.registered)
        check("状态栏文案（已注册）",
              manager.label(None).text() == f"已注册：{unit}")

        # 离屏环境下启动提示被跳过（不弹窗、不阻塞）
        skipped = registration.startup_prompt(None, Path(tmp) / "none.json", "PolyXRD-GetCIF")
        check("离屏跳过启动弹窗", not skipped.registered)

        # 手改状态文件伪造注册 → 必须失效
        data = json.loads(state_path.read_text(encoding="utf-8"))
        data["unit"] = "篡改单位"
        state_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        check("防手改伪造", not registration.load_state(state_path).registered)


def test_gui_smoke() -> None:
    """GUI 冒烟走子进程（QApplication 单例不可在同进程重建）。"""
    import subprocess

    root = Path(__file__).resolve().parent.parent
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONPATH"] = str(root / "src")
    result = subprocess.run(
        [sys.executable, "-m", "getcif.gui", "--smoke", "--no-splash"],
        capture_output=True, text=True, timeout=120, env=env, cwd=str(root),
    )
    check("GUI 离屏冒烟（子进程）", result.returncode == 0, result.stdout.strip()[-80:])


def test_internal_edition() -> None:
    """内部评估版链路（子进程）：无注册机制、状态栏「内部评估版本」、三语切换。"""
    import subprocess

    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, str(root / "tests" / "_internal_edition_check.py")],
        capture_output=True, text=True, timeout=120, cwd=str(root),
    )
    tail = (result.stdout or "").strip().splitlines()
    detail = tail[-1] if tail else (result.stderr or "").strip()[-120:]
    check("内部评估版链路（子进程）", result.returncode == 0, detail)


def test_cod_online() -> None:
    from getcif.adapters.cod import CodAdapter
    from getcif.core.schema import SearchQuery

    adapter = CodAdapter(timeout=30)
    cands = adapter.search(SearchQuery(formula="SiO2", limit=10))
    check("COD 在线检索", len(cands) > 0, f"total={adapter.last_total_count}")
    text = adapter.download_cif(cands[0])
    check("COD CIF 下载", bool(text) and "data_" in text, f"{len(text)} chars")
    from getcif.cifparse import parse_cif

    cif = parse_cif(text)
    check("COD CIF 解析渲染数据", bool(cif.sites) and cif.cell.get("a", 0) > 0)


def main() -> int:
    print("=" * 50)
    print("PolyXRD-GetCIF 发布前自检")
    print("=" * 50)
    test_cif_parse()
    test_mp_structure_to_cif()
    test_cod_local()
    test_polydb()
    test_xindb()
    test_theme_and_help_menu()
    test_viewer()
    test_registration()
    test_internal_edition()
    test_gui_smoke()
    if "--online" in sys.argv:
        test_cod_online()
    print("=" * 50)
    print("全部自检通过 ✔")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

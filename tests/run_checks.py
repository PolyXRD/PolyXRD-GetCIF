"""发布前自检脚本（无需 pytest，直接运行）::

    set PYTHONPATH=src
    python tests/run_checks.py          # 离线功能自检
    python tests/run_checks.py --online # 附加在线 COD 实测（需联网）

覆盖：CIF 解析（对称操作数值验证 / esd 剥离 / 分号多行块）、
MP structure → CIF、本地库检索过滤、3D 渲染、注册机制链路、GUI 离屏冒烟。
"""
from __future__ import annotations

import gzip
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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
    test_viewer()
    test_registration()
    test_gui_smoke()
    if "--online" in sys.argv:
        test_cod_online()
    print("=" * 50)
    print("全部自检通过 ✔")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

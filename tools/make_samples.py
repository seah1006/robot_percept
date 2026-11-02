"""cad_uploads/samples/ 에 테스트용 STEP 생성 (cadquery 형상, OCP STEPControl_Writer 로 단위 지정 저장)
cadquery.exporters.export 는 write.step.unit 을 무시하므로 writer 를 직접 사용한다."""
import re
from pathlib import Path

import cadquery as cq
from OCP.Interface import Interface_Static
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer

OUT = Path.home() / "work/robot_percept/cad_uploads/samples"
OUT.mkdir(parents=True, exist_ok=True)


def write(wp, name, unit="MM"):
    ok = Interface_Static.SetCVal_s("write.step.unit", unit)   # must be set before creating the writer
    w = STEPControl_Writer()
    w.Transfer(wp.val().wrapped, STEPControl_AsIs)
    p = OUT / f"{name}.step"
    w.Write(str(p))
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    txt = p.read_text(errors="ignore")
    units = re.findall(r"SI_UNIT\([^)]*\.METRE\.\)|CONVERSION_BASED_UNIT\('[^']*'", txt)
    print(f"{p.name:36s} unit={unit:5s} set_ok={ok} header={sorted(set(units))}")


box = cq.Workplane("XY").box(50, 30, 20).edges("|Z").fillet(3)
cup = cq.Workplane("XY").circle(35).extrude(60).faces(">Z").shell(-3)       # open-top cup, wall 3 mm
small = cq.Workplane("XY").box(2, 1.2, 0.8)                                   # "inch" numbers labelled mm

write(box, "box_fillet_50x30x20mm")
write(cup, "cup_d70_h60mm")
write(box, "box_fillet_metre_header", unit="M")
write(box, "box_fillet_cm_header", unit="CM")
write(box, "box_fillet_inch_header", unit="INCH")
write(small, "box_2x1.2x0.8_inch_mislabeled_mm")

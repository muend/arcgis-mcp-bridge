"""ToolSpecs + worker implementations — Category 6: Export & Layout.

All tools operate on saved .aprx projects via ``arcpy.mp`` (no live Pro
session access). Case-sensitivity guard: ``listLayouts``, ``exportToPDF``,
``exportToPNG``, ``listElements``, ``defaultView``, ``camera.setExtent``,
``pageWidth`` / ``pageHeight`` match Esri's arcpy.mp API exactly.
"""

from __future__ import annotations

from typing import Any

from ..contracts import export_layout as c
from ..registry import Category, ToolSpec, register


class LayoutTargetError(LookupError):
    """Layout, map frame or element named in the request does not exist."""


def _open_layout(
    arcpy: Any, aprx_path: str, layout_name: str | None
) -> tuple[Any, Any]:
    aprx = arcpy.mp.ArcGISProject(aprx_path)
    layouts = aprx.listLayouts(layout_name) if layout_name else aprx.listLayouts()
    if not layouts:
        raise LayoutTargetError(f"No layout matching {layout_name!r} in {aprx_path}")
    return aprx, layouts[0]


def _find_mapframe(layout: Any, name: str | None) -> Any:
    frames = (
        layout.listElements("MAPFRAME_ELEMENT", name)
        if name
        else layout.listElements("MAPFRAME_ELEMENT")
    )
    if not frames:
        raise LayoutTargetError(f"No map frame matching {name!r} in {layout.name!r}")
    return frames[0]


def _finish(aprx: Any, save: bool, **extra: Any) -> dict[str, Any]:
    if save:
        aprx.save()
    return {"saved": save, **extra}


# ------------------------------------------------------------------- tools --


def _list_layouts(arcpy: Any, inp: c.ListLayoutsInput) -> dict:
    aprx = arcpy.mp.ArcGISProject(inp.aprx_path)
    return {
        "layouts": [
            {
                "name": lt.name,
                "page_width": lt.pageWidth,
                "page_height": lt.pageHeight,
                "page_units": str(lt.pageUnits),
            }
            for lt in aprx.listLayouts()
        ]
    }


def _export_layout_pdf(arcpy: Any, inp: c.ExportLayoutPdfInput) -> dict:
    _, layout = _open_layout(arcpy, inp.aprx_path, inp.layout_name)
    layout.exportToPDF(
        inp.out_pdf, resolution=inp.resolution, image_quality=inp.image_quality
    )
    return {"output": inp.out_pdf, "layout": layout.name, "dpi": inp.resolution}


def _export_layout_png(arcpy: Any, inp: c.ExportLayoutPngInput) -> dict:
    _, layout = _open_layout(arcpy, inp.aprx_path, inp.layout_name)
    layout.exportToPNG(
        inp.out_png,
        resolution=inp.resolution,
        transparent_background=inp.transparent_background,
    )
    return {"output": inp.out_png, "layout": layout.name, "dpi": inp.resolution}


def _export_map_as_image(arcpy: Any, inp: c.ExportMapAsImageInput) -> dict:
    aprx = arcpy.mp.ArcGISProject(inp.aprx_path)
    maps = aprx.listMaps(inp.map_name) if inp.map_name else aprx.listMaps()
    if not maps:
        raise LayoutTargetError(f"No map matching {inp.map_name!r}")
    view = maps[0].defaultView
    view.exportToPNG(
        inp.out_png, width=inp.width, height=inp.height, resolution=inp.resolution
    )
    return {
        "output": inp.out_png,
        "map": maps[0].name,
        "pixels": [inp.width, inp.height],
    }


def _set_map_scale(arcpy: Any, inp: c.SetMapScaleInput) -> dict:
    aprx, layout = _open_layout(arcpy, inp.aprx_path, inp.layout_name)
    mf = _find_mapframe(layout, inp.map_frame)
    cam = mf.camera
    cam.scale = inp.scale
    return _finish(aprx, inp.save, map_frame=mf.name, scale=inp.scale)


def _set_map_extent_from_layer(arcpy: Any, inp: c.SetMapExtentFromLayerInput) -> dict:
    aprx, layout = _open_layout(arcpy, inp.aprx_path, inp.layout_name)
    mf = _find_mapframe(layout, inp.map_frame)
    layers = mf.map.listLayers(inp.layer_name)
    if not layers:
        raise LayoutTargetError(f"Layer {inp.layer_name!r} not found in frame map.")
    extent = mf.getLayerExtent(layers[0], False, True)
    mf.camera.setExtent(extent)
    return _finish(
        aprx,
        inp.save,
        map_frame=mf.name,
        layer=inp.layer_name,
        extent={
            "xmin": extent.XMin,
            "ymin": extent.YMin,
            "xmax": extent.XMax,
            "ymax": extent.YMax,
        },
    )


def _update_text_element(arcpy: Any, inp: c.UpdateTextElementInput) -> dict:
    aprx, layout = _open_layout(arcpy, inp.aprx_path, inp.layout_name)
    elements = layout.listElements("TEXT_ELEMENT", inp.element_name)
    if not elements:
        raise LayoutTargetError(
            f"Text element {inp.element_name!r} not found in {layout.name!r}."
        )
    old = elements[0].text
    elements[0].text = inp.new_text
    return _finish(aprx, inp.save, element=inp.element_name, old_text=old)


def _update_legend(arcpy: Any, inp: c.UpdateLegendInput) -> dict:
    aprx, layout = _open_layout(arcpy, inp.aprx_path, inp.layout_name)
    legends = (
        layout.listElements("LEGEND_ELEMENT", inp.legend_name)
        if inp.legend_name
        else layout.listElements("LEGEND_ELEMENT")
    )
    if not legends:
        raise LayoutTargetError(f"No legend element in layout {layout.name!r}.")
    legend = legends[0]

    if inp.action == "ADD":
        mf = _find_mapframe(layout, inp.map_frame)
        layers = mf.map.listLayers(inp.layer_name)
        if not layers:
            raise LayoutTargetError(f"Layer {inp.layer_name!r} not found to add.")
        legend.addItem(layers[0])
    else:
        items = [i for i in legend.items if i.name == inp.layer_name]
        if not items:
            raise LayoutTargetError(
                f"Legend item {inp.layer_name!r} not present; nothing to remove."
            )
        legend.removeItem(items[0])
    return _finish(
        aprx, inp.save, legend=legend.name, action=inp.action, layer=inp.layer_name
    )


def _set_layout_size(arcpy: Any, inp: c.SetLayoutSizeInput) -> dict:
    aprx, layout = _open_layout(arcpy, inp.aprx_path, inp.layout_name)
    old = (layout.pageWidth, layout.pageHeight)
    layout.pageWidth = inp.page_width
    layout.pageHeight = inp.page_height
    return _finish(
        aprx,
        inp.save,
        layout=layout.name,
        old_size=list(old),
        new_size=[inp.page_width, inp.page_height],
        page_units=str(layout.pageUnits),
    )


# -------------------------------------------------------------- registrations

_CAT = Category.EXPORT_LAYOUT

_SPECS = (
    (
        "list_layouts",
        (
            "List all layouts in a saved ArcGIS Pro .aprx project using "
            "arcpy.mp listLayouts. Use this to discover layout names, page sizes, "
            "and page units before exporting or modifying a layout. Reads the "
            "project only and does not save or mutate the .aprx file."
        ),
        c.ListLayoutsInput,
        _list_layouts,
    ),
    (
        "export_layout_pdf",
        (
            "Export a selected ArcGIS Pro layout to a PDF file using "
            "layout.exportToPDF. Use this for print-ready map sheets, reports, "
            "submittals, or archival exports with controlled DPI and image quality. "
            "Reads the .aprx project and writes out_pdf inside PathGuard allowed "
            "roots; existing files require overwrite=true."
        ),
        c.ExportLayoutPdfInput,
        _export_layout_pdf,
    ),
    (
        "export_layout_png",
        (
            "Export a selected ArcGIS Pro layout to a PNG image using "
            "layout.exportToPNG. Use this for previews, portfolio images, web "
            "graphics, or presentation-ready map layouts with controlled DPI and "
            "optional transparency. Reads the .aprx project and writes out_png "
            "inside PathGuard allowed roots."
        ),
        c.ExportLayoutPngInput,
        _export_layout_png,
    ),
    (
        "export_map_as_image",
        (
            "Export a map view directly to a PNG image using the map defaultView, "
            "without requiring a layout. Use this for quick map snapshots, previews, "
            "or automated image generation when a formal layout is unnecessary. "
            "Reads the .aprx project and writes out_png with the requested width, "
            "height, and resolution."
        ),
        c.ExportMapAsImageInput,
        _export_map_as_image,
    ),
    (
        "set_map_scale",
        (
            "Set the camera scale denominator for a selected layout map frame "
            "using arcpy.mp camera.scale. Use this before exporting a layout when "
            "the map must be fixed to a known scale such as 1:1000 or 1:50,000. "
            "This updates the .aprx project when save=true."
        ),
        c.SetMapScaleInput,
        _set_map_scale,
    ),
    (
        "set_map_extent_from_layer",
        (
            "Set a layout map frame extent to match a named layer using "
            "mf.getLayerExtent and mf.camera.setExtent. Use this before exporting "
            "a layout so the final map focuses on a dataset, study area, boundary, "
            "or analysis result. This changes the map frame camera and saves the "
            ".aprx project when save=true."
        ),
        c.SetMapExtentFromLayerInput,
        _set_map_extent_from_layer,
    ),
    (
        "update_text_element",
        (
            "Update the text content of a named layout text element using arcpy.mp "
            "layout elements. Use this to automate titles, dates, subtitles, map "
            "numbers, project names, notes, or report labels before export. This "
            "modifies the selected layout and saves the .aprx project when save=true."
        ),
        c.UpdateTextElementInput,
        _update_text_element,
    ),
    (
        "update_legend",
        (
            "Add or remove a layer entry in a selected layout legend using arcpy.mp "
            "legend addItem or removeItem. Use this to synchronize legends with "
            "automated layer changes before exporting maps. This modifies the "
            "layout legend and saves the .aprx project when save=true."
        ),
        c.UpdateLegendInput,
        _update_legend,
    ),
    (
        "set_layout_size",
        (
            "Change the physical page width and height of a selected ArcGIS Pro "
            "layout using layout.pageWidth and layout.pageHeight. Use this to "
            "switch between sheet sizes, portfolio formats, report pages, or "
            "print/export templates. This modifies the layout and saves the .aprx "
            "project when save=true."
        ),
        c.SetLayoutSizeInput,
        _set_layout_size,
    ),
)

for _name, _desc, _model, _fn in _SPECS:
    register(ToolSpec(_name, _CAT, _desc, _model, _fn))

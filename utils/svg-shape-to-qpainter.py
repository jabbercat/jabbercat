#!/usr/bin/python3
import svg.path


def unpack_coords(argv):
    for item in argv:
        if isinstance(item, complex):
            yield item.real
            yield item.imag
        else:
            yield item


def process_argv(argv):
    for item in argv:
        if isinstance(item, complex):
            yield "Qt.QPointF({!r}, {!r})".format(
                item.real,
                item.imag,
            )
        else:
            yield repr(item)


def translate(p, translation):
    return complex(p.real + translation[0],
                   p.imag + translation[1])


def translate_all(argv, translation):
    for item in argv:
        if isinstance(item, complex):
            yield translate(item, translation)
        else:
            yield item


def convert_path(s, translation):
    path = svg.path.parse_path(s)

    commands = [
        "path = Qt.QPainterPath()"
    ]

    def compose_command(cmd, argv):
        commands.append(
            "{}({})".format(
                cmd,
                ", ".join(process_argv(argv)),
            )
        )

    prev_endpoint = None
    for el in path:
        if el.start != prev_endpoint:
            cmd = "path.moveTo"
            argv = unpack_coords(translate_all((el.start,), translation))
            compose_command(cmd, argv)
        prev_endpoint = el.end

        if isinstance(el, svg.path.CubicBezier):
            cmd = "path.cubicTo"
            argv = unpack_coords(translate_all(
                (el.control1, el.control2, el.end),
                translation,
            ))
            compose_command(cmd, argv)

        elif isinstance(el, svg.path.Line):
            cmd = "path.lineTo"
            argv = unpack_coords(translate_all(
                (el.end,),
                translation,
            ))
            compose_command(cmd, argv)

        else:
            raise TypeError(
                "unsupported path element: {}".format(el)
            )

    return "\n".join(commands)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--translate",
        dest="translation",
        nargs=2,
        metavar=("X", "Y"),
        type=float,
        default=(0, 0),
    )
    parser.add_argument(
        "path"
    )

    args = parser.parse_args()

    print(convert_path(args.path, args.translation))

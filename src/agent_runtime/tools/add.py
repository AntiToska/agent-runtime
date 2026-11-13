"""Input model for the addition tool."""

from pydantic import BaseModel, ConfigDict, ValidationError


class AddArgs(BaseModel):
    # 开启Pydantic的严格模式
    model_config = ConfigDict(strict=True)

    a: int
    b: int


def add(args: AddArgs) -> int:
    return args.a + args.b


if __name__ == "__main__":
    # 正常输入
    args = AddArgs(a=1, b=2)
    result = add(args)
    print(result)
    # 错误输入
    try:
        args = AddArgs.model_validate({"a": "1", "b": 2})
    except ValidationError as error:
        print("参数不合法：")
        print(error)

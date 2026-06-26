from app.workers.tasks.parse_price import parse_price


def main() -> None:
    result = parse_price.delay(
        123,
    )

    print(
        f"Task sent: {result.id}",
    )


if __name__ == "__main__":
    main()

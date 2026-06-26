from app.workers.tasks.parse_price import parse_price


if __name__ == "__main__":
    result = parse_price.delay(123)

    print(result.id)

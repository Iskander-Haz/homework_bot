import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if (
        PRACTICUM_TOKEN is None
        or TELEGRAM_TOKEN is None
        or TELEGRAM_CHAT_ID is None
    ):
        raise (
            Exception('Переменная не определена')
            and logger.critical(
                'отсутствие обязательных переменных окружения '
                'во время запуска бота'
            )
        )
    else:
        return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправлено')
    except Exception as error:
        logger.error(f'Сбой при отправке сообщения в Telegram: {error}')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except requests.RequestException:
        logger.error('Ошибка при запросе к основному API', exc_info=True)
    if homework_statuses.status_code != HTTPStatus.OK:
        raise (
            Exception(
                f'Запрос не успешный. '
                f'Код ответа {homework_statuses.status_code} отличный от 200'
            )
            and logger.error('Недоступность эндпоинта')
        )
    else:
        return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if type(response) is dict:
        if (
            'current_date' in response.keys()
            and 'homeworks' in response.keys()
        ):
            if type(response['homeworks']) is list:
                return True
            else:
                raise (
                    Exception(
                        'Ответ API не соответствие документации. '
                        'homeworks не список'
                    )
                    and logger.error(
                        'Отсутствие ожидаемых ключей в ответе API'
                    )
                )
        else:
            raise (
                Exception('Ответ API не соответствие документации. '
                          'Не верные ключи')
                and logger.error('Отсутствие ожидаемых ключей в ответе API')
            )
    else:
        raise (
            Exception('Ответ API не соответствие документации. Не словарь')
            and logger.error('Отсутствие ожидаемых ключей в ответе API')
        )


def parse_status(homework):
    """Извлекает из информации о домашней работе статус."""
    try:
        verdict = HOMEWORK_VERDICTS[homework['status']]
    except KeyError:
        logger.error('Неожиданный статус домашней работы.')

    try:
        homework_name = homework['homework_name']
    except KeyError:
        logger.error('когда в ответе API домашки нет ключа "homework_name".')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if check_tokens():
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        timestamp = int(time.time())     # для тестирования 1678884576
        while True:

            try:
                response = get_api_answer(timestamp)
                timestamp = response.get('current_date')
                if check_response(response):
                    try:
                        homework = response.get('homeworks')[0]
                        send_message(bot, parse_status(homework))
                    except IndexError:
                        logger.debug(
                            'Не появился новый статус — список работ пуст'
                        )
            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                logger.error(message, exc_info=True)
                send_message(bot, message)
            finally:
                time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info('*** Остановка программы ***')

import scrapy

# Golf is priced per round per player unless a venue truly charges another way.
PRICE_UNIT_PER_ROUND = "per_round"


class TeeTimeItem(scrapy.Item):
    """One bookable slot. Every spider yields this shape and nothing else.

    starts_at is an aware datetime in UTC. course_slug matches courses.yaml id
    and courses.slug. The pipeline resolves it to the integer course id.
    """

    course_slug = scrapy.Field()
    starts_at = scrapy.Field()
    holes = scrapy.Field()
    spots_available = scrapy.Field()
    price_per_player = scrapy.Field()
    currency = scrapy.Field()
    price_unit = scrapy.Field()
    booking_url = scrapy.Field()

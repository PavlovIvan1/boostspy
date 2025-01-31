from api.schemas import *
from database.requests import (get_active_season, get_daily_boost, and_,
                               get_daily_boosts, get_referres, create_transaction, get_transaction,
                               get_user_daily_boost, get_user_wallet, set_user, get_party_related_users, get_finished_season, get_party_leaderboard, get_party_members,
                               set_user_daily_boost, get_party_member)
from fastapi import APIRouter, HTTPException, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from middlewares import webapp_user_middleware
from ton_requests import get_account_nft, AdminWallet, get_twif_balance
from database.models import Party, PartyMember, MemberStatusEnum, generate_uuid, Transaction

router = APIRouter(prefix='/boosts', tags=['Бусты и Игра'])


@router.get('/daily', response_model=AllDailyBoost)
async def get_all_daily_boosts():
    boosts = await get_daily_boosts()
    return JSONResponse(status_code=200, content=jsonable_encoder(boosts))


@router.post('/user_daily_boost', response_model=DailyBoost)
@webapp_user_middleware
async def get_user_boosts_for_nft(request: WebAppRequest, initData: InitDataRequest):
    daily_boost = await get_user_daily_boost(user_id=request.webapp_user.id)

    if daily_boost is None:
        raise HTTPException(status_code=400, detail='No daily boost selected')

    return JSONResponse(status_code=200, content=jsonable_encoder(daily_boost.boost))


@router.post('/set_user_daily_boost', response_model=DailyBoost)
@webapp_user_middleware
async def select_user_daily_boost(request: WebAppRequest, boost: SetUserDailyBoost):
    _boost = await get_daily_boost(boost_id=boost.boost_id)

    if request.webapp_user.stars < _boost.stars:
        raise HTTPException(
            status_code=400, detail='You do not have enough stars')

    await set_user_daily_boost(user_id=request.webapp_user.id, boost_id=boost.boost_id)
    await set_user(user_id=request.webapp_user.id, stars=request.webapp_user.stars - _boost.stars)

    return Response(status_code=200)


@router.post('/create_link', response_model=DailyBoost)
@webapp_user_middleware
async def select_user_daily_boost(request: WebAppRequest, boost: SetUserDailyBoost):
    _boost = await get_daily_boost(boost_id=boost.boost_id)
    print(_boost)
    def create_invoice(self, price_value, payload):
        prices = [telebot.types.LabeledPrice(label="Image Purchase", amount=int(price_value))]

        payment_link = bot.create_invoice_link(
            title="Image Purchase",
            description="Purchase an image for 1 star!",
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=prices
        )
        return payment_link

    def create_token(self, user):
        payload_token = random.randint(10 ** 15, 10 ** 16 - 1)
        token = Tokens.objects.create(user=user, payloadtoken=payload_token, is_paid=False)
        return token.payloadtoken

    @action(detail=False, methods=['post'])
    def create_boost_stars(self, request):
        tg_id = self.request.tg_user_data.get('tg_id', None)
        user = get_object_or_404(Users, tg_id=tg_id)
        data = request.query_params.get('data', None)

        if not data:
            return Response({"detail": "Squad name not provided."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            squad = Squads.objects.get(channelname=data)
        except Squads.DoesNotExist:
            return Response({"detail": "Squad not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            price = Price.objects.get(ticker='boost_squad')
        except Price.DoesNotExist:
            return Response({"detail": "Boost price not found."}, status=status.HTTP_404_NOT_FOUND)

        payload_token = self.create_token(user)
        payment_link = self.create_invoice(float(price.stars), payload_token)

        return Response({'payment_link': payment_link, 'payload_token': payload_token, 'ready_to_pay': True},
                        status=status.HTTP_201_CREATED)




@router.post('/get_nft_boosts', response_model=UserBoostsForNFT)
@webapp_user_middleware
async def get_user_boosts_for_nft(request: WebAppRequest, initData: InitDataRequest):
    wallet = await get_user_wallet(user_id=request.webapp_user.id)

    if wallet is None:
        raise HTTPException(
            status_code=400, detail='You should connect your wallet')

    result = dict(white=1, black=1, silver=1, gold=1, result=1)
    extra = dict(white=1.1, black=1.4, silver=2.5, gold=10)
    nft_items = await get_account_nft(wallet.address)
    for nft in nft_items:
        result[nft['color']] *= extra[nft['color']]
        result['result'] *= extra[nft['color']]

    return UserBoostsForNFT(boosts=result)


MINUTES = 10


@router.post('/get_attempts')
@webapp_user_middleware
async def get_attempts(request: WebAppRequest, initData: InitDataRequest):
    if request.webapp_user.attempts < 6:
        dif = datetime.now(timezone.utc) - request.webapp_user.last_attempt
        dif: timedelta
        new_attempts = min(request.webapp_user.attempts +
                           dif.seconds // (60 * MINUTES), 6)

        if new_attempts != request.webapp_user.attempts:
            la = datetime.now(
                timezone.utc) if request.webapp_user.last_attempt is None else request.webapp_user.last_attempt + timedelta(minutes=MINUTES)
            await set_user(user_id=request.webapp_user.id, attempts=new_attempts, last_attempt=la)

        return JSONResponse(status_code=200, content=jsonable_encoder({
            'attempts': new_attempts
        }))

    return JSONResponse(status_code=200, content=jsonable_encoder({'attempts': 6}))


@router.post('/add_attempt')
@webapp_user_middleware
async def get_attempts(request: WebAppRequest, initData: InitDataRequest):
    if request.webapp_user.attempts < 6:
        new_attempts = request.webapp_user.attempts + 1

        la = datetime.now(timezone.utc)
        await set_user(user_id=request.webapp_user.id, attempts=new_attempts, last_attempt=la)

    return JSONResponse(status_code=200, content=jsonable_encoder({'detail': 'success'}))


@router.post('/save_game')
@webapp_user_middleware
async def save_game(request: WebAppRequest, game: SaveGame):
    if request.webapp_user.attempts == 6:
        await set_user(user_id=request.webapp_user.id, last_attempt=datetime.now(timezone.utc))

    await set_user(user_id=request.webapp_user.id, attempts=request.webapp_user.attempts - 1, points=request.webapp_user.points + game.points)

    referres = await get_referres(user=request.webapp_user)
    for i in range(len(referres)):
        bonus = int(game.points / 100 * (3-i))
        await set_user(user_id=referres[i], points=referres[i].points + bonus)

    return Response(status_code=200)


@router.get('/deadline')
async def get_deadline(request: Request):
    season = await get_active_season()

    if not season:
        raise HTTPException(status_code=404, detail='No one active season')

    deadline = season.deadline.strftime("%d.%m.%Y %H:%M")

    return JSONResponse(status_code=200, content=jsonable_encoder({
        'deadline': deadline
    }))


@router.get('/finished_season')
async def finished_season(request: Request):
    season = await get_finished_season()

    if not season:
        raise HTTPException(status_code=404, detail='No finished season')

    return JSONResponse(status_code=200, content=jsonable_encoder({
        'season': season.title
    }))


@router.post('/claim')
@webapp_user_middleware
async def finished_season(request: WebAppRequest, initData: InitDataRequest):
    leader_party: Party = (await get_party_leaderboard(limit=1))[0][0]

    if not leader_party:
        raise HTTPException(status_code=400, detail='No winner found')

    members: List[PartyMember] = await get_party_members(leader_party.id)

    if not request.webapp_user.id in [member.member.id for member in members]:
        raise HTTPException(status_code=400, detail='You could not get reward')

    wallet = await get_user_wallet(user_id=request.webapp_user.id)

    if not wallet:
        raise HTTPException(status_code=400, detail='Connect your wallet')

    member_status: MemberStatusEnum = await get_party_member(party_id=leader_party.id, user_id=request.webapp_user.id)

    pull = await get_twif_balance(account_id=AdminWallet.user_friendly_address)

    part: int = 0
    if member_status.value == 'creator':
        part = pull * leader_party.founder_share

    if member_status.value == 'founder':
        part = pull * leader_party.founder_share

    if member_status.value == 'member':
        part = pull * leader_party.members_share

    if member_status.value == 'voter':
        part = pull * leader_party.voters_share

    amount = 0
    for member in members:
        if member.member_status == member_status:
            member_wallet = await get_user_wallet(user_id=member.member_id)

            if member_wallet:
                _transaction = await get_transaction(and_(Transaction.wallet_id == member_wallet.id, Transaction.payload == leader_party.id))
                if not _transaction:
                    amount += 1
                elif member.member_id == request.webapp_user.id:
                    raise HTTPException(status_code=400, detail='You have already requested your reward')

    my_part = part / amount * 0.95

    AdminWallet.transfer_twif(destination_address=wallet.address, amount=my_part)
    await create_transaction(event_id=generate_uuid(), wallet_id=wallet.id, payload=leader_party.id)

    return JSONResponse(status_code=200, content=jsonable_encoder({'detail': f'You will receive {round(my_part, 2)} twif'}))

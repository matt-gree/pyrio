import os
import json
from .api_manager import include_rio_key, APIManager

if os.path.exists('rio_key.json'):
    with open('rio_key.json', "r") as config_file:
        global RIO_KEY
        RIO_KEY = json.load(config_file)['rio_key']
else:
    print("WARNING: 'rio_key.json' file does not exist.")
    RIO_KEY = ''

debug_mode = True

def debug_print(data):
    if debug_mode:
        # Mask the RIO key if it is in data
        masked_data = data.copy()  # Create a copy to avoid modifying the original
        if 'RIO_KEY' in masked_data:
            masked_data['RIO_KEY'] = '****'  # Mask the key with asterisks or whatever you prefer
        
        print(masked_data)

### example of including the decorator. I'd also like to think that you could streamline the params part too but I didn't have anything come to mind right now
@include_rio_key(RIO_KEY)
def create_community(api_manager: APIManager, community_name_free, private, global_link, comm_desc, comm_type="Unofficial", data=None):
    ### this is because of the decorator, by using it, the args for the function get kinda wonky, so the way to fix it is to pass it data so that what it is expecting is there
    
    ENDPOINT = "/community/create"
    
    if data is None:
        data = {}

    ### because of above, just update data, not create new one
    data.update({
        "community_name": community_name_free,
        "type": comm_type, # Official or Unnoficial
        "private": private, # True or False
        "global_link": global_link, # True or False
        "desc": comm_desc,
    })

    debug_print(data)

    ### calls api manager and sends the request
    return api_manager.send_request(ENDPOINT, method="POST", data=data)


@include_rio_key(RIO_KEY)
def community_invite(api_manager: APIManager, community_name_closed, invite_list, data=None):

    ENDPOINT = "/community/invite"

    if data is None:
        data = {}

    data.update({
        "community_name": community_name_closed,
        "invite_list": invite_list
    })

    return api_manager.send_request(ENDPOINT, method="POST", data=data)


@include_rio_key(RIO_KEY)
def community_members(api_manager: APIManager, community_name_closed, data=None):

    ENDPOINT = "/community/members"

    if data is None:
        data = {}

    data.update({
        "community_name": community_name_closed,
    })
    ''' 
    Example Output:

    {'Members': [{'active': True, 'admin': True, 'banned': None, 'date_joined': 1706937663, 'id': 2496, 
    'invited': False, 'user_id': 375}, {'active': True, 'admin': False, 'banned': None,
    'date_joined': 1706938397, 'id': 2497, 'invited': True, 'user_id': 28}
    '''
    return api_manager.send_request(ENDPOINT, method="POST", data=data)


@include_rio_key(RIO_KEY)
def community_tags(api_manager: APIManager, community_name_closed, data=None):

    ENDPOINT = "/community/tags"

    if data is None:
        data = {}

    data.update({
        "community_name": community_name_closed,
    })
    ''' 
    Example Output:

    {'Tags': [{'active': True, 'comm_id': 18, 'date_created': 1706937663,
    'desc': 'Community tag for Netplay Superstars', 'id': 131, 'name': 'Netplay Superstars', 'type': 'Community'},
    {'active': True, 'comm_id': 18, 'date_created': 1706938057, 'desc': 'Netplay Superstars 16', 'id': 132,
    'name': 'Netplay Superstars 16', 'type': 'Competition'}, {'active': True, 'comm_id': 18,
    'date_created': 1712881215, 'desc': 'NPSS17', 'id': 147, 'name': 'NPSS17', 'type': 'Competition'}
    '''
    return api_manager.send_request(ENDPOINT, method="POST", data=data)


@include_rio_key(RIO_KEY)
def community_manage(api_manager: APIManager, community_name_closed, user_list, data=None):

    ENDPOINT = "/community/manage"

    if data is None:
        data = {}

    '''
    user_list = [
        {
            "username": "USERNAME",
            "admin": True/False
            "remove": True/False
            "ban": True/False
            "key": True/False

        }, ...
    ]
    '''

    data.update({
        "community_name": community_name_closed,
        'user_list': user_list
    })

    debug_print(data)
    
    return api_manager.send_request(ENDPOINT, method="POST", data=data)


@include_rio_key(RIO_KEY)
def community_sponsor(api_manager: APIManager, community_name_closed, action, data=None):

    ENDPOINT = "/community/sponsor"

    if data is None:
        data = {}

    data.update({
        "community_name": community_name_closed,
        'action': action # Get, Remove or Add
    })

    debug_print(data)

    '''
    Example Outputs

    action = generate/revoke:
    [{'active': True, 'admin': True, 'banned': False, 'community_key': None, 'date_joined': 1706487496,
    'date_key_created': None, 'id': 2055, 'invited': True, 'user_id': 55}]

    action = generate_all
    [{'comm_key': 'fqwI', 'user': 'VicklessFalcon'}, {'comm_key': 'thUp', 'user': 'MattGree'}]

    '''
    
    return api_manager.send_request(ENDPOINT, method="POST", data=data)


@include_rio_key(RIO_KEY)
def community_key(api_manager: APIManager, community_name_closed, key_action, data=None):

    ENDPOINT = "/community/key"

    if data is None:
        data = {}

    data.update({
        "community_name": community_name_closed,
        'action': key_action # generate, revoke, generate_all
    })

    debug_print(data)
    
    return api_manager.send_request(ENDPOINT, method="POST", data=data)


@include_rio_key(RIO_KEY)
def community_update(
    api_manager: APIManager,
    community_id: str,
    community_name_free: str = None,
    comm_desc: str = None,
    comm_type: str = None,
    private: bool = None,
    global_link: bool = None,
    active_tag_set_limit: int = None,
    data: dict = None
):
    ENDPOINT = "/community/update"

    if data is None:
        data = {}

    # Required field
    data["community_id"] = community_id

    # Add optional fields only if they are not None
    if community_name_free is not None:
        data["name"] = community_name_free
    if comm_desc is not None:
        data["desc"] = comm_desc
    if comm_type is not None:
        data["type"] = comm_type  # Official or Unofficial
    if global_link is not None:
        data["link"] = global_link  # True or False
    if private is not None:
        data["private"] = private  # True or False
    if active_tag_set_limit is not None:
        data["active_tag_set_limit"] = active_tag_set_limit  # Int

    debug_print(data)

    return api_manager.send_request(ENDPOINT, method="POST", data=data)


@include_rio_key(RIO_KEY)
def create_tag(api_manager: APIManager, tag_name_free, tag_desc, community_name_closed, tag_type, gecko_code_desc=None, gecko_code=None, data=None):

    ENDPOINT = '/tag/create'

    if data is None:
        data = {}

    data.update({
        'name': tag_name_free,
        'desc': tag_desc,
        'community_name': community_name_closed,
        'type': tag_type,
    })

    if tag_type == 'Gecko Code':
        data.update({
            'gecko_code_desc': gecko_code_desc,
            'gecko_code': gecko_code,
        })

    debug_print(data)
    
    return api_manager.send_request(ENDPOINT, method="POST", data=data)


@include_rio_key(RIO_KEY)
def update_tag(api_manager: APIManager, tag_id, tag_name_free=None, tag_desc=None, tag_type=None, gecko_code_desc=None, gecko_code=None, data=None):
    ENDPOINT = '/tag/update'

    if data is None:
        data = {}

    data['tag_id'] = tag_id

    if tag_name_free is not None:
        data['name'] = tag_name_free
    if tag_desc is not None:
        data['desc'] = tag_desc
    if tag_type is not None:
        data['type'] = tag_type
    
    if tag_type == 'Gecko Code':
        if gecko_code is not None:
            data['gecko_code'] = gecko_code
        if gecko_code_desc is not None:
            data['gecko_code_desc'] = gecko_code_desc

    debug_print(data)

    return api_manager.send_request(ENDPOINT, method="POST", data=data)


@include_rio_key(RIO_KEY)
def list_tags(api_manager: APIManager, tag_type=None, community_ids=None, data=None):
    
    ENDPOINT = "/tag/list"

    if data is None:
        data = {}

    if tag_type:
        data['Types'] = tag_type

    if community_ids:
        data['community_ids'] = community_ids

    # Make the API request
    return api_manager.send_request(ENDPOINT, method="POST", data=data)


@include_rio_key(RIO_KEY)
def create_game_mode(api_manager: APIManager, game_mode_name_free, game_mode_desc, game_mode_type, community_name_closed, start_date, end_date, add_tag_ids=None, game_mode_to_mirror_tags_from=None, data=None):
    
    ENDPOINT = "/tag_set/create"

    if data is None:
        data = {}

    data.update({
        'name': game_mode_name_free,
        'desc': game_mode_desc,
        'type': game_mode_type,
        'community_name': community_name_closed,
        'start_date': start_date,
        'end_date': end_date,
    })

    if add_tag_ids:
        data['add_tag_ids'] = add_tag_ids

    if game_mode_to_mirror_tags_from:
        data['tag_set_id'] = game_mode_to_mirror_tags_from

    debug_print(data)

    return api_manager.send_request(ENDPOINT, method="POST", data=data)


@include_rio_key(RIO_KEY)
def delete_game_mode(api_manager: APIManager, game_mode_name_closed, data=None):
    
    ENDPOINT = "/tag_set/delete"

    if data is None:
        data = {}

    data.update({
        'name': game_mode_name_closed,
    })

    debug_print(data)

    return api_manager.send_request(ENDPOINT, method="POST", data=data)


@include_rio_key(RIO_KEY)    
def list_game_modes(api_manager: APIManager, active=False, community_ids=None, data=None):

    ENDPOINT = "/tag_set/list"

    if data is None:
        data = {}

    if active:
        data['Active'] = active

    if community_ids:
        data['Communities'] = community_ids

    return api_manager.send_request(ENDPOINT, method="POST", data=data)


@include_rio_key(RIO_KEY)
def list_game_mode_tags(api_manager: APIManager, tag_set_id, data=None):
    
    ENDPOINT = f"/tag_set/{tag_set_id}"

    return api_manager.send_request(ENDPOINT, method='GET')


@include_rio_key(RIO_KEY)
def update_game_mode(api_manager: APIManager, tag_set_id, game_mode_name_free=None, game_mode_desc=None, game_mode_type=None, start_date=None, end_date=None, add_tag_ids=None, remove_tag_ids=None, data=None):
    
    ENDPOINT = "/tag_set/update"

    if data is None:
        data = {}

    data.update({
        'tag_set_id': tag_set_id
    })

    # Add arguments to data dict if they are not None
    if game_mode_name_free is not None:
        data['game_mode_name_free'] = game_mode_name_free
    if game_mode_desc is not None:
        data['game_mode_desc'] = game_mode_desc
    if game_mode_type is not None:
        data['game_mode_type'] = game_mode_type
    if start_date is not None:
        data['start_date'] = start_date
    if end_date is not None:
        data['end_date'] = end_date
    if add_tag_ids is not None:
        data['add_tag_ids'] = add_tag_ids
    if remove_tag_ids is not None:
        data['remove_tag_ids'] = remove_tag_ids

    debug_print(data)

    return api_manager.send_request(ENDPOINT, method='POST', data=data)


@include_rio_key(RIO_KEY)
def game_mode_ladder(api_manager: APIManager, game_mode_name_closed, data=None):
    
    ENDPOINT = "/tag_set/ladder"

    if data is None:
        data = {}

    data['TagSet'] = game_mode_name_closed

    return api_manager.send_request(ENDPOINT, method='POST', data=data)


def list_users(api_manager: APIManager):
    return api_manager.send_request('/user/all')
  

@include_rio_key(RIO_KEY)
def delete_game(api_manager: APIManager, game_id_dec):
    
    ENDPOINT = "/delete_game/"

    if data is None:
        data = {}

    data['game_id'] = game_id_dec

    return api_manager.send_request(ENDPOINT, method='POST', data=data)

# Don't use @include_rio_key bc of the json key difference
def manual_game_submit(api_manager: APIManager, winner_username, winner_score, loser_username, loser_score, date, tag_set, recalc=True, game_id_hex=None, game_id_dec=None, data=None):

    ENDPOINT = "/manual_submit_game/"

    data = {
        'winner_username': winner_username,
        'winner_score': winner_score,
        'loser_username': loser_username,
        'loser_score': loser_score,
        'date': date,
        'tag_set': tag_set,
        'submitter_rio_key': RIO_KEY,
        'recalc': recalc
    }
    if game_id_dec:
        data.update({'game_id_ded': game_id_dec})
    if game_id_hex:
        data.update({'game_id_hex': game_id_hex})

    debug_print(data)

    return api_manager.send_request(ENDPOINT, method='POST', data=data)


@include_rio_key(RIO_KEY)
def add_user_to_user_group(api_manager: APIManager, username, group_name, data=None):
    
    ENDPOINT = '/user_group/add_user'

    if data is None:
        data = {}

    data['username'] =  username
    data['group_name'] = group_name

    debug_print(data)

    return api_manager.send_request(ENDPOINT, method='POST', data=data)


@include_rio_key(RIO_KEY)
def check_for_member_in_user_group(api_manager: APIManager, username, group_name, data=None):
    
    ENDPOINT = '/user_group/check_for_member'

    if data is None:
        data = {}

    data['username'] = username
    data['group_name'] = group_name

    debug_print(data)

    return api_manager.send_request(ENDPOINT, method='GET', data=data)


@include_rio_key(RIO_KEY)
def remove_user_from_user_group(api_manager: APIManager, username, group_name, data=None):
    
    ENDPOINT = '/user_group/remove_user'

    if data is None:
        data = {}

    data['username'] = username
    data['group_name'] = group_name

    debug_print(data)

    return api_manager.send_request(ENDPOINT, method='POST', data=data)


def check_members_of_user_groups(api_manager: APIManager, group_name):
    
    ENDPOINT = '/user_group/members'

    data = {}
    data['group_name'] = group_name

    debug_print(data)

    return api_manager.send_request(ENDPOINT, method='GET', data=data)

# Games
def games_endpoint(api_manager: APIManager, tag=None, exclude_tag=None, username=None, vs_username=None, exclude_username=None, captain=None, vs_captain=None, stadium=None, limit_games=None):

    ENDPOINT = '/games'
    
    data = {}

    if tag:
        data['tag'] = tag
    if exclude_tag:
        data['exclude_tag'] = tag
    if username:
        data['username'] = username
    if vs_username:
        data['vs_username'] = vs_username
    if exclude_username:
        data['exclude_username'] = exclude_username
    if captain:
        data['captain'] = captain
    if vs_captain:
        data['vs_captain'] = vs_captain
    if stadium:
        data['stadium'] = stadium
    if limit_games:
        data['limit_games'] = limit_games

    debug_print(data)

    return api_manager.send_request(ENDPOINT, method='GET', data=data)




if __name__ == '__main__':
    sample_inputs = {
        'community_name_closed': 'Netplay Superstars',
    }
    manager = APIManager()
    print(community_tags(manager, sample_inputs['community_name_closed']))


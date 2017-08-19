from django.shortcuts import render, redirect
from forms import SignUpForm, LoginForm, PostForm, LikeForm, CommentForm, UpvoteForm
from models import UserModel, SessionToken, PostModel, LikeModel, CommentModel, UpvoteModel
from django.contrib.auth.hashers import make_password, check_password
from datetime import timedelta
from django.utils import timezone
from mysite.settings import BASE_DIR
from keys import CLIENT_SECRET, CLIENT_ID, CLARIFI_API_KEY, SENDGRID_API_KEY, FROM_EMAIL,CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET, CLOUDINARY_ENVIRONMENT_VARIABLE
import sendgrid
from sendgrid.helpers.mail import *
import cloudinary
import cloudinary.uploader
import cloudinary.api
from imgurpython import ImgurClient
from clarifai.rest import ClarifaiApp
from django.contrib import messages

cloudinary.config(
  cloud_name = "mycloud",
  api_key = CLOUDINARY_API_KEY,
  api_secret = CLOUDINARY_API_SECRET
)

# views here.

# Sign up
def signup_view(request):

    # Storing data for sendgrid api
    user_data={}

    if request.method == "POST":

        form = SignUpForm(request.POST)

        if form.is_valid():

            # Getting the form data
            username = form.cleaned_data['username']

            name = form.cleaned_data['name']

            email = form.cleaned_data['email']

            password = form.cleaned_data['password']

            # Validating the data
            if len(username)>3 and len(password)>4 and len(name)>0 and len(email)>0:

                # saving data to DB
                user = UserModel(name=name, password=make_password(password), email=email, username=username)

                user.save()

                user_data['to_email'] = email

                user_data['subject'] = 'Smart P2P MarketPlace'

                user_data['content'] = 'Signup sucessful on Smart P2P Marketplace'

                # Sending mail to the new user
                sendmail(user_data)

                # redirecting the user
                return render(request, 'success.html')

                # return redirect('login/')

            else:

                # Using built in messages view to display alerts
                messages.error(request, 'Username should have min 4 characters and password should have 5. No field should be empty')

    else:

        form = SignUpForm()

    return render(request, 'index.html', {'form': form})

# Login view
def login_view(request):

    response_data = {}

    if request.method == "POST":

        form = LoginForm(request.POST)

        if form.is_valid():

            username = form.cleaned_data.get('username')

            password = form.cleaned_data.get('password')

            # Finding user in dB
            user = UserModel.objects.filter(username=username).first()

            if user:

                # Authenticating user
                if check_password(password, user.password):

                    # Preparing session token
                    token = SessionToken(user=user)

                    token.create_token()

                    token.save()

                    response = redirect('feed/')

                    # Setting cookies for easier experience
                    response.set_cookie(key='session_token', value=token.session_token)

                    messages.info(request, "LogIn successful! Enjoy!")

                    return response

                else:

                    messages.error(request, "Invalid credentials! Try again!")

    elif request.method == 'GET':

        form = LoginForm()

    response_data['form'] = form

    return render(request, 'login.html', response_data)

# View for uploading posts
def post_view(request):

    # Checking if the user is logged in
    user = check_validation(request)

    if user:

        if request.method == 'POST':

            form = PostForm(request.POST, request.FILES)

            if form.is_valid():

                image = form.cleaned_data.get('image')

                caption = form.cleaned_data.get('caption')

                # Saving the post
                post = PostModel(user=user, image=image, caption=caption)

                post.save()

                # Preparing path for saving the image
                path = str(BASE_DIR +'/'+ post.image.url)

                #client = cloudinary.uploader.upload(path)

                #post.image_url = client['url']

                client = ImgurClient(CLIENT_ID, CLIENT_SECRET)

                # Using imgur to get image url for easier access
                post.image_url = client.upload_from_path(path, anon=True)['link']

                post.save()

                # Using Clarifai to categorise the image
                app = ClarifaiApp(api_key=CLARIFI_API_KEY)

                model = app.models.get('general-v1.3')

                result = model.predict_by_url(post.image_url)

                post.category = result['outputs'][0]['data']['concepts'][0]['name']

                # Saving the post details
                post.save()

                messages.info(request, "Post Successful!")

                return redirect('/feed/')

        else:

            form = PostForm()

            messages.error(request, 'Post unsuccessful! Try again!')

        return render(request, 'post.html', {'form': form})

    else:

        return redirect('/login/')

# Setting the feed
def feed_view(request):

    user = check_validation(request)

    if user:

        # Sorting posts based on creation date
        posts = PostModel.objects.all().order_by('created_on')

        # Checking likes, comments and upvotes on the posts
        for post in posts:

            existing_like = LikeModel.objects.filter(post_id=post.id, user=user).first()

            for comment in post.comments:

                existing_upvote = UpvoteModel.objects.filter(comment=comment.id, user=user).first()

                if existing_upvote:

                    comment.has_upvoted = True

            if existing_like:

                post.has_liked = True

        # Rendering the posts to feed template
        return render(request, 'feed.html', {'posts': posts})

    else:

        return redirect('/login/')

# Like controller
def like_view(request):

    user = check_validation(request)

    # Saving data for sendgrid
    user_data={}

    if user and request.method == 'POST':

        form = LikeForm(request.POST)

        if form.is_valid():

            post_id = form.cleaned_data.get('post')

            user_data['to_email'] = form.cleaned_data.get('post').user.email

            # Checking if already liked
            existing_like = LikeModel.objects.filter(post_id = post_id, user=user).first()

            # If not then liked
            if not existing_like:

                LikeModel.objects.create(post=post_id, user=user)

                user_data['subject'] = 'Liked'

                user_data['content'] = 'Your post was liked by ' + form.cleaned_data.get('post').user.name

                sendmail(user_data)

            # Otherwise unliked
            else:

                existing_like.delete()

                user_data['subject'] = 'Unliked'

                user_data['content'] = 'Your post was unliked by ' + form.cleaned_data.get('post').user.name

                sendmail(user_data)

            return redirect('/feed/')

    else:

        return redirect('/login/')

# Comment controller
def comment_view(request):

    # You should know this by now
    user_data = {}

    user = check_validation(request)

    if user and request.method == 'POST':

        form = CommentForm(request.POST)

        if form.is_valid():

            post_id = form.cleaned_data.get('post').id

            user_data['to_email'] = form.cleaned_data.get('post').user.email

            user_data['subject'] = 'Commented'

            user_data['content'] = 'Your post was commented by ' + form.cleaned_data.get('post').user.name

            #Getting comment form data
            comment_text = form.cleaned_data.get('comment_text')

            # Saving comment in dB
            comment = CommentModel.objects.create(user=user, post_id=post_id, comment_text=comment_text)

            comment.save()

            sendmail(user_data)

            messages.info(request, 'Your comment has been posted!')

            return redirect('/feed/')

        else:

            return redirect('/feed/')

    else:

        return redirect('/login')

# Upvote controller (as in reddit )
def upvote_view(request):
    user = check_validation(request)

    user_data = {}

    if user and request.method == 'POST':

        form = UpvoteForm(request.POST)

        if form.is_valid():

            comment_id = form.cleaned_data.get('comment')

            user_data['to_email'] = form.cleaned_data.get('comment').user.email

            # Checking upvotes on comments:>
            existing_upvote = UpvoteModel.objects.filter(comment_id=comment_id, user=user).first()

            # If not then upvote
            if not existing_upvote:

                UpvoteModel.objects.create(comment=comment_id, user=user)

                user_data['subject'] = 'Upvoted'

                user_data['content'] = 'Your comment was upvoted by ' + form.cleaned_data.get('comment').user.name

                sendmail(user_data)

            # Otherwise downvote(opposie of upvoting :<
            else:

                existing_upvote.delete()

                user_data['subject'] = 'Downvoted'

                user_data['content'] = 'Your comment was downvoted by ' + form.cleaned_data.get('comment').user.name

                sendmail(user_data)

            return redirect('/feed/')

    else:

        return redirect('/login/')


# For validating the session
def check_validation(request):

    if request.COOKIES.get('session_token'):

        # Getting related session token from dB
        session = SessionToken.objects.filter(session_token=request.COOKIES.get('session_token')).first()

        # Checking the expiration date
        if session:

            time_to_live = session.created_on + timedelta(days=1)

            if time_to_live > timezone.now():

                return session.user
    else:

        return None

#To logout a user
def logout_view(request):
    user = check_validation(request)

    if user:

        # Flushing the session from the database:)
        SessionToken.objects.filter(session_token=request.COOKIES.get('session_token')).first().delete()

        return redirect('/login/')

    else:

        return redirect('/login/')

# Sending mails to everyone
def sendmail(user_data):

    sg = sendgrid.SendGridAPIClient(apikey=SENDGRID_API_KEY)

    from_email = Email(FROM_EMAIL)

    to_email = Email(user_data['to_email'])

    subject = user_data['subject']

    content = Content("text/plain", user_data['content'])

    mail = Mail(from_email, subject, to_email, content)

    response = sg.client.mail.send.post(request_body=mail.get())


# Url query 
def query_view(request):

    user = check_validation(request)

    uid = int(request.GET.get('uid', user.id))

    if user:

        posts = PostModel.objects.filter(user=uid).order_by('created_on')

        for post in posts:

            existing_like = LikeModel.objects.filter(post_id=post.id, user=user).first()

            for comment in post.comments:

                existing_upvote = UpvoteModel.objects.filter(comment_id=comment.id, user=user).first()

                if existing_upvote:
                    comment.has_upvoted = True

            if existing_like:
                post.has_liked = True

        return render(request, 'feed.html', {'posts': posts})

    else:

        return redirect('/login/')





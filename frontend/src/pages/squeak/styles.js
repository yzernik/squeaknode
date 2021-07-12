import { makeStyles } from "@material-ui/styles";

export default makeStyles(theme => ({
  dashedBorder: {
    border: "1px dashed",
    borderColor: theme.palette.primary.main,
    padding: theme.spacing(2),
    paddingTop: theme.spacing(4),
    paddingBottom: theme.spacing(4),
    marginTop: theme.spacing(1),
  },
  text: {
    marginBottom: theme.spacing(2),
  },
  oppositeContent: {
  // TODO: adjust this value accordingly
    flex: 0.0,
    padding: 0,
  },
  dummyContent: {
  // TODO: use a relative height of the containing element.
    minHeight: "500px",
  }
}));

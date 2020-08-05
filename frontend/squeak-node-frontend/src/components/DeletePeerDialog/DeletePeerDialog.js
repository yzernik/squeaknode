import React, {useState, useEffect} from 'react';
import {
  Paper,
  IconButton,
  Menu,
  MenuItem,
  Typography,
  Grid,
  Box,
  Link,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  TextField,
  DialogActions,
  Button,
  FormControl,
  InputLabel,
  Select,
} from "@material-ui/core";
import { MoreVert as MoreIcon } from "@material-ui/icons";
import {useHistory} from "react-router-dom";
import classnames from "classnames";

// styles
import useStyles from "./styles";

import Widget from "../../components/Widget";

import {
  DeletePeerRequest,
} from "../../proto/squeak_admin_pb"
import {SqueakAdminClient} from "../../proto/squeak_admin_grpc_web_pb"

var client = new SqueakAdminClient('http://' + window.location.hostname + ':8080')

export default function DeletePeerDialog({
  open,
  handleClose,
  peer,
  ...props
}) {
  var classes = useStyles();
  const history = useHistory();

  const deletePeer = (peerId) => {
    console.log("called deleteSqueak");

    var deletePeerRequest = new DeletePeerRequest()
    deletePeerRequest.setPeerId(peerId);
    console.log(deletePeerRequest);

    client.deletePeer(deletePeerRequest, {}, (err, response) => {
      if (err) {
        console.log(err.message);
        alert('Error deleting peer: ' + err.message);
        return;
      }

      console.log(response);
      reloadRoute();
    });
  };

  const reloadRoute = () => {
    history.go(0);
  };

  function handleSubmit(event) {
    event.preventDefault();
    console.log( 'peer:', peer);
    var peerId = peer.getPeerId();
    console.log( 'peerId:', peerId);
    deletePeer(peerId);
    handleClose();
  }

  function MakeCancelButton() {
    return (
      <Button
        onClick={handleClose}
        variant="contained"
        color="secondary"
      >
        Cancel
      </Button>
    )
  }

  function DeletePeerButton() {
    return (
      <Button
       type="submit"
       variant="contained"
       color="primary"
       className={classes.button}
       >
        Delete peer
       </Button>
    )
  }

  return (
    <Dialog open={open} onClose={handleClose} aria-labelledby="form-dialog-title">
  <DialogTitle id="form-dialog-title">Delete peer</DialogTitle>
  <form className={classes.root} onSubmit={handleSubmit} noValidate autoComplete="off">
  <DialogContent>
    Are you sure you want to delete this peer?
  </DialogContent>
  <DialogActions>
    {MakeCancelButton()}
    {DeletePeerButton()}
  </DialogActions>
  </form>
    </Dialog>
  )
}
